# Import packages
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


TOKEN_FILE = "noridgen_tokens.json"
SECRET_FILE = "secret_file.json" 

IDs: List = ["REVOLUT_REVOGB21","BARCLAYS_BUKBGB22","AMERICAN_EXPRESS_AESUGB21"]
IDs_names: List = ["Revolut","Barclays","Amex"]
IDs_names_map: Dict = dict(zip(IDs,IDs_names))


# Nordigen Client Management
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



def re_auth2(bank: str ,wait_time: int = 4) -> "str":
    print(f"Connecting to: {IDs_names_map[bank]}")

    redirect_uri: str ="https://gocardless.com"
    # Open connection for the bank
    session = client.initialize_session(
        institution_id=bank,
        redirect_uri= redirect_uri,
        reference_id=str(uuid4())
    )

    out = f"{session.link}"
    return out

def get_id_from_name(key: str) -> str:
    if key not in IDs_names_map.values():
        raise Exception ("Name not in Dictionary")
    index_val = list(IDs_names_map.values()).index(key)
    out = list(IDs_names_map)[index_val]
    return out





