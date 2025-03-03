from nordigen import NordigenClient
from uuid import uuid4
import pandas as pd
import os
from datetime import datetime as dt
from datetime import timedelta
import json
import time
import openai
from typing import Dict, List, Tuple, Union
import sqlite3
import requests
import warnings 
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys

warnings.simplefilter(action='ignore', category=FutureWarning)

TOKEN_FILE = "noridgen_tokens.json"
SECRET_FILE = "secret_file.json" 


# Fetch Transaction Data - Functions


def save_tokens(token_data: Dict) -> None:
    token_data["last_run"] = dt.now().isoformat()
    with open(TOKEN_FILE,"w") as file:
        json.dump(token_data,file, indent = 4)
        print("New tokens saved")

def load_tokens()-> Dict:
    with open(TOKEN_FILE,"r") as file: 
        return json.load(file)

def load_secret_data()-> Dict:
    with open(SECRET_FILE,"r") as file: 
        return json.load(file)

def assign_tokens() -> Dict:

    global client
    
    client = NordigenClient(
    secret_id= load_secret_data()["Nordigen_id"],
    secret_key= load_secret_data()["Nordigen_key"]
    )

    token_data: Dict = load_tokens()
    out = token_data
    if token_data != None: 
        try:
            token_data = client.exchange_token(refresh_token=token_data["refresh"])
            print("Token refreshed")
        except:
            token_data = client.generate_token()
            save_tokens(token_data)
            out = token_data
    else:
        token_data = client.generate_token()
        save_tokens(token_data)
        out = token_data

    try:
        client.token = token_data["access"]
        print("Token assigned")
    except:
        raise Exception("An error has occured with token assignment")

    return out

def get_timestamp()-> pd.Timestamp:
    with open(TOKEN_FILE,"r") as file:
        data = json.load(file)
        if "last_run" in data:
            return dt.fromisoformat(data["last_run"])
        else:
            print("Timestamp not found in the token file.")

def refresh_token_check() -> pd.Timestamp:
    refresh_expiry: int = load_tokens()["refresh_expires"]

    return get_timestamp()+timedelta(seconds=refresh_expiry)<dt.now()

def re_auth(bank: str ,wait_time: int = 4) -> "accounts":
    print(f"Connecting to: {IDs_names_map[bank]}")

    redirect_uri: str ="https://gocardless.com"
    # Open connection for the bank
    session = client.initialize_session(
        institution_id=bank,
        redirect_uri= redirect_uri,
        reference_id=str(uuid4())
    )

    print(f"Authorisation link for {bank}: {session.link}")
    requisition_id = session.requisition_id

    accounts = client.requisition.get_requisition_by_id(requisition_id=requisition_id)

    flag: int = 0
    counter: int = 0
    while accounts["status"] != "LN":
        accounts = client.requisition.get_requisition_by_id(requisition_id=requisition_id)
        
        if flag == 0:
            flag += 1
            counter +=1
            print(f"Waiting for confirmation from {IDs_names_map[bank]}")
            time.sleep(10)
            continue
        else:
            print("Still waiting...")
            time.sleep(10)
    
        if counter > wait_time*6:
            print(f"Waited {wait_time} minutes for confirmation!")
            print("Will break here - please investigate further)")
            break
    else:
        print("Auth confirmed! Status is linked :^)")


    return accounts


def fetch_account_data(accounts: "accounts" ,bank: str) -> Dict:
    for account_id in accounts["accounts"]:
        account = client.account_api(id=account_id)
        
        transactions: Dict = account.get_transactions()["transactions"]
        balances: Dict = account.get_balances()["balances"]
        details: Dict = account.get_details()
        
        account_data = {
            "Bank ID": bank,
            "Bank Name": IDs_names_map[bank],
            "Account ID": account_id,
            "Details": details,
            "Balances": balances,
            "Transactions":transactions
        }
        return account_data
        

def fetch_requisitions() -> pd.DataFrame: 
    fetch_requisition = client.requisition.get_requisitions()
    requisitions_result_df: pd.DataFrame = pd.DataFrame(fetch_requisition["results"])
    
    linked_ids_df: pd.DataFrame = requisitions_result_df[requisitions_result_df.status == "LN"]
    linked_ids_df.sort_values(by = "created",ascending = False, axis = 0, inplace = True)
    linked_ids_df = linked_ids_df[linked_ids_df.institution_id.duplicated() == False]
    linked_ids_df.index: pd.Series = linked_ids_df.institution_id.values

    linked_ids_df = linked_ids_df.to_dict("index")

    return linked_ids_df
    

# Chatgpt Integration - Functions

def google_search(query: str, num_results: int = 5) -> Dict:
    url: str = "https://www.googleapis.com/customsearch/v1"

    params = {
    "q": query,
    "cx": search_engine_id,
    "key": google_key,
    "num": num_results
    }

    response: "response"  = requests.get(url, params= params)
    response.raise_for_status()

    data = response.json()
    return data.get("items",[])

def get_snippet(result: List[Dict]) -> str: 
    try:
        snippet = result[0]["snippet"].split(".")[0]
        return snippet
    except:
        return " "

def categorise_transactions_with_search(description: str) -> str:

    result = google_search(description)
    snippet = get_snippet(result)

    response = open_ai_client.chat.completions.create(
        model = "gpt-3.5-turbo-0125",
        messages = [{"role": "system", "content": role},
                     {"role": "user", "content": f"Categorise this transaction: {description} (Context: {snippet})"}
                   ]
    )
    response_dict[description] = response
    return response.dict()["choices"][0]["message"]["content"]


google_key: str = load_secret_data()["google_key"]
search_engine_id: str = "3668be8d637cb4b30"

OPEN_API_KEY = load_secret_data()["OPEN_AI_KEY"]
openai.api_key = OPEN_API_KEY
open_ai_client = openai.OpenAI(api_key= OPEN_API_KEY)


groups: Tuple = ("Transport", "Groceries & Supermarkets", "Dining & Takeaways", "Retail & Shopping", "Entertainment", "Miscellaneous","Income","Household")

conditions: Tuple = ("Exclude Apple pay Top-up", 
              "Transactions with UBS in them should be classified in Dining & Takeaways", 
              "Exclude transactions containing Payment Received",
              "Cash machine withdrawals should be placed in Miscellaneous",
              "Transactions to people should be in Miscellaneous", 
              "Transactions with openai should be in Miscellaneous",
             )

role: str  = f"You are an expert personal financial advisor who will categorise my transactions into these groups: {groups}, it is crucial you keep these conditions in mind: {conditions}"


# Post-Processing - Functions

def post_processing(df: pd.DataFrame) -> pd.DataFrame:
    df.amount = df.amount.astype(float)
    df = df.reset_index(drop = True)
    df.bookingDateTime = df.bookingDateTime.apply(pd.to_datetime)
    df["month"] = df.bookingDateTime.apply(lambda x: x.month)
    df["year"] = df.bookingDateTime.apply(lambda x: x.year)
    df["day"] = df.bookingDateTime.apply(lambda x: x.day)

    return df

def compress_response_to_groups(output: str, groups: Union[List,Tuple]  = groups) -> str:
    for val in groups: 
        group = val.lower()
        if group in output.lower():
            return val
        else:
            continue
    return pd.NA

def manual_adjustments(df: pd.DataFrame) -> pd.DataFrame:
    # Transactions to savings - Barclays side
    savings_to_adjust_index: pd.Index = df[df.transaction_description.str.contains("204628")].index
    df.loc[savings_to_adjust_index,"classification"] = "Exclude"

    # Credit Card payments - Barclays side
    amex_payments_to_adjust_index: pd.Index = df[(df.bank == "Barclays") &(df.transaction_description.str.contains("AMERICAN"))].index
    df.loc[amex_payments_to_adjust_index, "classification"] = "Exclude"

    # Credit Card payments - Amex Side
    amex_payments_to_adjust_index2: pd.Index = df[(df.bank == "Amex") &(df.transaction_description.str.contains("PAYMENT"))].index
    df.loc[amex_payments_to_adjust_index2, "classification"] = "Exclude"

    # Revolut Transfers - Barclays side
    revolut_transers_to_adjust_index: pd.Index = df[(df.bank == "Barclays") & (df.transaction_description.str.contains("Revolut"))].index
    df.loc[revolut_transers_to_adjust_index,"classification"] = "Exclude"

    return df


# Database management - Functions 

def query_builder_last_two_months() -> str:
    today: pd.Timestamp = dt.today()
    current_month: int = today.month
    current_year: int = today.year

    if (current_month -1) == 0:
        last_month: int = 12
        last_year: int = current_year - 1
    else:
        last_month: int = current_month-1
        last_year: int = current_year

    query: str = f""" 
    SELECT* FROM transactions
    WHERE month = {current_month} AND year = {current_year} 
    OR 
        month = {last_month} AND year = {last_year}
    """
    return query

def last_two_months()-> pd.DataFrame: 
    out: pd.DataFrame = pd.read_sql_query(query_builder_last_two_months(), conn)
    return out 


def drop_settled_transactions(ids: Tuple) -> None: 
    query: str = "DELETE FROM transactions WHERE id in ({})".format(", ".join("?" * len(ids)))
    cursor.execute(query, ids)
    print(f"Rows dropped: {ids}")

def get_transactions_year(year: int = dt.today().year) -> pd.DataFrame: 
    query: str = f"""
    SELECT* FROM transactions
    Where year = {year}
    """

    out: pd.DataFrame = pd.read_sql_query(query, conn)
    return out

conn = sqlite3.connect("transactions.db")
cursor = conn.cursor()

# Email - Functions 

def send_email(email_type: str, section: str = None, error: str = None, ids_list: list = None, new_transactions: pd.DataFrame = None) -> None: 
    if email_type not in ["update","confirmation", "error"]:
        raise Exception("email_type must be 'update' or 'confirmation'")

    sender_email = "j4647188@gmail.com"
    receiver_email = "ayoolukotun00@gmail.com"
    password = load_secret_data()["email_password"]

    today_str = dt.today().strftime("%Y-%m-%d")

    

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email

    

    
    
    if email_type == "update":

        missing_banks_list = [IDs_names_map[key] for key in ids_list]
        ids_string = " \n".join(missing_banks_list)

        Subject = today_str +" - Expired Authentications"
        string = "These connections need to be updated:" + "\n \n"+ ids_string
        body = MIMEText(string, "plain")

    elif email_type == "confirmation":
        Subject = today_str +" - Budget Updated Successfully"
        html = """\
                <html>
                  <head></head>
                  <body>
                  <b>Database has been updated</b>
                  <p>New Transactions added:</p>
                    {0}
                  </body>
                </html>
                """.format(new_transactions.to_html())
        body = MIMEText(html, "html")
    else:
        error = str(error)
        Subject = today_str +" - An Error Has Occured"
        string = section + "\n\n" + error
        body = MIMEText(string, "plain")
        

    msg["Subject"] = Subject
    msg.attach(body)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
            print("Email sent successfully!")
    except Exception as e:
        print(f"Error: {e}")
            



if __name__ == "__main__":

# Fetch Transaction Data
    try:
        IDs: List = ["REVOLUT_REVOGB21","BARCLAYS_BUKBGB22","AMERICAN_EXPRESS_AESUGB21"]
        IDs_names: List = ["Revolut","Barclays","Amex"]
        IDs_names_map: Dict = dict(zip(IDs,IDs_names))
        all_accounts_data: List = []
    
    
        token_data = assign_tokens()
        requisition_ID_dict = fetch_requisitions()
        missing_ids: List = list(set(IDs)-set(requisition_ID_dict.keys()))
        
        if refresh_token_check() or len(missing_ids) != 0:
            send_email(email_type="update", ids_list= missing_ids)
            sys.exit()
        
        for bank_id in requisition_ID_dict:
            print(bank_id)
            account = requisition_ID_dict[bank_id]
            account_data = fetch_account_data(accounts= account, bank= bank_id)
            all_accounts_data.append(account_data)


        transaction_dfs_list: List = []
        for bank_info in all_accounts_data:
            temp_list: List = []
            for status in bank_info["Transactions"].keys():
                temp_df = (pd.DataFrame(bank_info["Transactions"][status]))
                temp_df["status"] = status
                temp_list.append(temp_df)
        
            bank_transaction_df = pd.concat(temp_list)
            bank_transaction_df["bank"] = bank_info["Bank Name"]
            transaction_dfs_list.append(bank_transaction_df)
        
        transactions_df: pd.DataFrame = pd.concat(transaction_dfs_list)


        relevant_df: pd.DataFrame =  transactions_df[["bookingDateTime","transactionAmount","creditorName","remittanceInformationUnstructuredArray","remittanceInformationUnstructured","bank","status"]]
        relevant_df[["amount","currency"]] = relevant_df.transactionAmount.apply(lambda x: pd.Series((x["amount"],x["currency"])))
        relevant_df["transaction_description"] = relevant_df[["remittanceInformationUnstructuredArray", "remittanceInformationUnstructured"]].bfill(axis=1).iloc[:,0]
        relevant_df.transaction_description = relevant_df.transaction_description.apply(lambda x: x[0] if type(x) == list else x)
        relevant_df.drop(labels = ["transactionAmount","remittanceInformationUnstructuredArray","remittanceInformationUnstructured"], axis = 1, inplace = True)

        relevant_df["classification"] = pd.NA


    except Exception as e:
        section = "Fetch Transaction Data"
        error = str(e)
        send_email(email_type="error", section=section, error=error) 



    
    # Database Storage
    try: 
        to_db_df: pd.DataFrame = post_processing(relevant_df.copy())
        to_db_df = manual_adjustments(to_db_df)
        to_db_df.bookingDateTime = to_db_df.bookingDateTime.apply(lambda x: str(x))

        # add id columns 
        to_db_df["id"] = pd.NA 

        # assign id to id column
        cursor.execute("UPDATE transactions SET id = rowid;");
        
        # Call last two months of data from db
        last_two_months_df: pd.DataFrame = last_two_months()

        # Identify similar rows across new transactions and db query
        columns_to_compare: List = ["day", "month", "year","amount","bank","creditorName"]
        common_rows: pd.DataFrame = pd.merge(to_db_df,last_two_months_df, on= columns_to_compare, how = "inner",suffixes= ("_new","_old") )


        # Create dataframe to append to db 
        max_date: dt  = last_two_months_df.apply(lambda x: dt(x.year, x.month, x.day), axis =1).max()
        to_db_df_filtered: pd.DataFrame = to_db_df[(~to_db_df.isin(common_rows).all(axis=1)) &(to_db_df.apply(lambda x: dt(x.year, x.month, x.day), axis =1) > max_date)]


        # Add Commentary from chatgpt
        response_dict: Dict = {}
        chatgpt_output: pd.Series = to_db_df_filtered.transaction_description.apply(lambda x : categorise_transactions_with_search(x))
        to_db_df_filtered["classification"] = chatgpt_output


        # Compress Classifications to groups
        groups_list: list = list(groups)
        groups_list.append("Exclude")
        
        to_db_df_filtered.classification = to_db_df_filtered.classification.apply(lambda x: compress_response_to_groups(x, groups = groups_list))


        # Identify transactions that have settled and drop them from db
        settled_rows: pd.DataFrame = common_rows[(common_rows.status_new == "booked") & (common_rows.status_old == "pending")]
        ids_to_drop: Tuple = tuple(settled_rows.id_old.values)
        drop_settled_transactions(ids_to_drop)

        # Append new transactions to the db 
        to_db_df_filtered.to_sql("transactions", con= conn, if_exists= "append", index = False) # append new data

        cursor.execute("UPDATE transactions SET id = rowid;");
        conn.close()


        send_email(email_type="confirmation", new_transactions= to_db_df_filtered)

    except Exception as e:
        section = "Database storage"
        error = str(e)
        send_email(email_type="error", section=section, error=error)
    
        
    








