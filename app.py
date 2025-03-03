from flask import Flask, render_template,request, jsonify
import sqlite3
from typing import Dict, List, Tuple, Union
from datetime import datetime as dt
import pandas as pd
import warnings
import Fetch_Transactions_functions as ftf

warnings.simplefilter(action= "ignore", category=FutureWarning)

# Add code to get rid of warnings 

# <------ API functions ------>
database_name: str = "transactions.db"

def get_db_connection() -> sqlite3.Connection:
    conn: sqlite3.Connection = sqlite3.connect("transactions.db")

    return conn

def get_transactions_year(conn: sqlite3.Connection, year: int = dt.today().year, ) -> pd.DataFrame: 
    query: str = f"""
    SELECT* FROM transactions
    Where year = {year}
    """

    out: pd.DataFrame = pd.read_sql_query(query, conn)

    return out


def get_expenditure_year(conn: sqlite3.Connection, year: int = dt.today().year, month_as_str = True) -> pd.DataFrame:

    cursor = conn.cursor()
    cursor.execute("UPDATE transactions SET id = rowid;")
    conn.commit()

    raw_data: pd.DataFrame = get_transactions_year(year = year, conn= conn)
    expenditure: pd.DataFrame = raw_data[raw_data.amount <=0]

    if month_as_str: 
        expenditure.month = expenditure.month.apply(lambda x: dt(year = 2000, month = x, day = 1).strftime("%b"))
    
    return expenditure 


def add_total(df: pd.DataFrame) -> pd.DataFrame:
    total = df.sum(axis =1)
    total.name = "Total"
    output = pd.concat([df,total], axis = 1)

    return output


# <------ APP ------>

app: Flask = Flask(__name__)

@app.route("/api/grouped-expenditure", methods=["GET"])
def api_grouped_expenditure(year: int = dt.today().year ) -> "Response": # Year input here is irrelevant - remove
    conn: sqlite3.Connection = get_db_connection()

    year = request.args.get("year", default = dt.today().year, type= int)

    expenditure: pd.DataFrame =  get_expenditure_year(year = year, conn= conn)
    expenditure = expenditure[(expenditure.classification != "Exclude") & (expenditure.classification != "Income")]
    grouped: pd.api.typing.DataFrameGroupBy = expenditure.groupby(["month","classification"])["amount"].sum().unstack(fill_value = 0).T
    grouped = grouped *-1

    grouped_with_total = add_total(grouped).round(2)
    
    conn.close()
    return jsonify(grouped_with_total.reset_index().to_dict(orient="records"))


@app.route("/api/breakdown-by-bank", methods = ["GET"])
def api_breakdown_by_bank(year: int = dt.today().year) -> "Response": # Year input here is irrelevant - remove
    conn = get_db_connection()

    year = request.args.get("year", default = dt.today().year, type= int)

    expenditure: pd.DataFrame = get_expenditure_year(year = year, conn= conn)
    expenditure = expenditure[(expenditure.classification != "Exclude") & (expenditure.classification != "Income")]
    grouped: pd.api.typing.DataFrameGroupBy = expenditure.groupby(["month","bank","classification"])["amount"].sum().unstack(level = 0, fill_value=0)
    grouped = grouped *-1

    grouped_with_total = add_total(grouped).round(2)

    conn.close()
    return jsonify(grouped_with_total.reset_index().to_dict(orient="records"))


@app.route("/api/expenditure-trends", methods = ["GET"])

def api_expenditure_trends(year: int = dt.today().year) -> "Response":
    conn = get_db_connection()

    year = request.args.get("year", default = dt.today().year, type= int)
    
    expenditure: pd.DataFrame = get_expenditure_year(year=year, conn= conn, month_as_str=False)
    expenditure = expenditure[expenditure.classification != "Exclude"]
    grouped: pd.api.typing.DataFrameGroupBy = expenditure.groupby(["month","bank","classification"])["amount"].sum().fillna(0)
    grouped = grouped *-1
    grouped = grouped.reset_index()

    conn.close()
    return jsonify(grouped.to_dict(orient = "records"))


@app.route("/api/transaction-details", methods = ["GET"])
def api_transaction_details()-> "Response": 

    conn: sqlite3.Connection = get_db_connection()

    category: str = request.args.get("category")
    month: int = request.args.get("month", type= int)
    year: int = request.args.get("year", default = dt.today().year, type= int)

    query: str = f"""
            SELECT * FROM transactions
            Where classification = ? AND month = ? AND year = ?
            """

    transactions: pd.DataFrame = pd.read_sql_query(query, conn, params = (category, month, year))

    rel_transactions = transactions[["bookingDateTime", "amount","bank","transaction_description","id","classification"]]
    rel_transactions.bookingDateTime = rel_transactions.bookingDateTime.apply(lambda x: x[:11])
    rel_transactions.amount = rel_transactions.amount *-1

    conn.close()
    return jsonify(rel_transactions.to_dict(orient= "records"))

@app.route("/api/update-category", methods = ["POST"])
def update_category() -> "Response":
    data = request.json
    
    transaction_id = data["transaction_id"]
    new_category = data["new_category"]

    conn: sqlite3.Connection = get_db_connection()
    conn.execute("UPDATE transactions SET classification =? WHERE id = ?", (new_category,transaction_id))
    conn.commit()
    conn.close()


    return jsonify({"message": f"Category updated successfully - {transaction_id}"})


@app.route("/api/reauthenticate", methods = ["GET"])
def reauthenticate() -> "Response":

    ftf.assign_tokens()

    bank = request.args.get("bank")
    bank_id = ftf.get_id_from_name(bank)

    reauth_link = ftf.re_auth2(bank_id)
    return jsonify({"link": reauth_link})



@app.route("/")
def index():
    print("loading index page")
    return render_template("page1_v4.html")


@app.route("/trends")
def trends():
    return render_template("page2.html")


@app.route("/page1")
def page1():
    return render_template("page1_v4.html")

@app.route("/page2")
def page2():
    return render_template("page2.html")



if __name__ == "__main__":
    print("starting flask application")
    app.run(debug= True)