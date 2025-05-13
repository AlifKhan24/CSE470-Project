from flask import Flask, request, redirect, render_template, flash, url_for, make_response, jsonify
import pymysql
import bcrypt
import datetime
import random
from datetime import datetime, date, timedelta
import string
import threading
from time import sleep
from decimal import Decimal
import logging
import time
import traceback
from flask import jsonify
from flask import jsonify, session
from dateutil.relativedelta import relativedelta
import os
from flask import send_file, request, redirect
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import os
from werkzeug.utils import secure_filename



logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)
app.secret_key = 'your_secret_key_here' 

db = pymysql.connect(
    host="localhost",
    user="root",
    password=" ", #Your Password
    database="mobilebanking",
    cursorclass=pymysql.cursors.DictCursor  
)



#Helper Functions
def get_user_id_from_cookie():
    return request.cookies.get("user_id")

def set_secure_cookie(response, user_id):
    response.set_cookie("user_id", str(user_id), max_age=3600, httponly=True, secure=True, samesite='Strict')
    return response

def get_db_connection():
    return db

def generate_unique_trx_id(cursor):
    while True:
        trx_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        cursor.execute("SELECT trx_id FROM send_money WHERE trx_id = %s", (trx_id,))
        if not cursor.fetchone():
            return trx_id

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def add_months(start_date, months):
    year = start_date.year + ((start_date.month - 1 + months) // 12)
    month = (start_date.month - 1 + months) % 12 + 1
    day = min(start_date.day, [31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
    return date(year, month, day)

@app.route("/logout")
def logout():
    resp = make_response(redirect("/login"))
    resp.delete_cookie("user_id")
    return resp


####  MD Alif Khan Shafi ###
#send_money_internationally
@app.route('/submit_transaction', methods=['POST'])
def submit_transaction():
    user_id = get_user_id_from_cookie()
    if not user_id:
        return jsonify({'success': False, 'message': 'User not logged in'}), 401
    try:
        data = request.get_json()
        account_no = data.get('account_no')
        receivers_name = data.get('receivers_name')
        amount = float(data.get('amount'))
        country = data.get('country')
        # Store data in temporary_send_money_international 
        with db.cursor() as cursor:
            trx_id = generate_unique_trx_id(cursor)
            # Delete existing temporary transactions for this user
            cursor.execute("DELETE FROM temporary_send_money_international WHERE user_id = %s", (user_id,))            
            query = """
            INSERT INTO temporary_send_money_international (trx_id, account_no, receivers_name, amount, country, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (trx_id, account_no, receivers_name, amount, country, user_id))
            db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        print(f"Error in submit_transaction: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/int_money_confirm_transaction')
def int_money_confirm_transaction():
    user_id = get_user_id_from_cookie()
    if not user_id:
        return redirect("/login")
    try:
        with db.cursor() as cursor:
            # Retrieving the transaction for current user
            query = """SELECT * FROM temporary_send_money_international 
                    WHERE user_id = %s"""
            cursor.execute(query, (user_id,))
            transaction = cursor.fetchone()
        if not transaction:
            return redirect("/send_money_int")
        exchange_rates = {
            'Australia': 77.27,
            'Canada': 85.05,
            'China': 16.67,
            'France': 131.64,
            'Germany': 131.64,
            'Saudi Arabia': 32.39
        }
        amount_in_bdt = float(transaction['amount'])
        country = transaction['country']
        exchange_rate = exchange_rates.get(country, 1)
        amount_in_selected_country = round(amount_in_bdt / exchange_rate, 2)        
        print(f"Debug - Country: {country}, Exchange rate: {exchange_rate}")
        print(f"Debug - Amount in BDT: {amount_in_bdt}, Amount in {country}: {amount_in_selected_country}")
        context = {
            'account_no': transaction['account_no'],
            'receivers_name': transaction['receivers_name'],
            'country': country,
            'amount_in_bdt': amount_in_bdt,
            'amount_in_selected_country': amount_in_selected_country,
            'user_id': user_id,
            'trx_id': transaction['trx_id']
        }
        return render_template('int_money_confirm.html', **context)   
    except Exception as e:
        print(f"Error in int_money_confirm_transaction: {str(e)}")
        return redirect("/send_money_int")

@app.route('/confirm_send_money', methods=['POST'])
def confirm_send_money():
    user_id = get_user_id_from_cookie()
    if not user_id:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401
    try:
        # Log incoming form data
        print("Form data received:")
        for key, value in request.form.items():
            print(f"{key}: {value}")

        # Extract form data
        account_no = request.form.get('account_no', '')
        receivers_name = request.form.get('receivers_name', '')
        country = request.form.get('country', '')
        trx_id = request.form.get('trx_id', '')

        try:
            amount_in_bdt = float(request.form.get('amount_in_bdt', '0'))
        except ValueError:
            print("Invalid amount_in_bdt value")
            amount_in_bdt = 0

        try:
            amount_in_selected_country = float(request.form.get('amount_in_selected_country', '0'))
        except ValueError:
            print("Invalid amount_in_selected_country value")
            amount_in_selected_country = 0

        # Check for missing/invalid values
        if not all([account_no, receivers_name, country, trx_id]) or amount_in_bdt <= 0 or amount_in_selected_country <= 0:
            missing_fields = []
            if not account_no: missing_fields.append("account_no")
            if not receivers_name: missing_fields.append("receivers_name")
            if not country: missing_fields.append("country")
            if not trx_id: missing_fields.append("trx_id")
            if amount_in_bdt <= 0: missing_fields.append("amount_in_bdt")
            if amount_in_selected_country <= 0: missing_fields.append("amount_in_selected_country")
            error_msg = f"Missing or invalid fields: {', '.join(missing_fields)}"
            print(error_msg)
            return jsonify({'status': 'error', 'message': error_msg})

        with db.cursor() as cursor:
            # Fetch user data
            cursor.execute("SELECT balance, transaction_limit FROM user_profile WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                print(f"User with ID {user_id} not found")
                return jsonify({'status': 'error', 'message': 'User not found'})

            if user['transaction_limit'] < amount_in_bdt:
                return jsonify({'status': 'error', 'message': 'Transaction limit reached. Increase your transaction limit to continue.'})

            if user['balance'] < amount_in_bdt:
                print(f"Insufficient balance. User has {user['balance']}, needs {amount_in_bdt}")
                return jsonify({'status': 'error', 'message': 'Insufficient balance for this transaction'})

            # Check temporary transaction
            cursor.execute("SELECT * FROM temporary_send_money_international WHERE trx_id = %s AND user_id = %s", 
                          (trx_id, user_id))
            temp_transaction = cursor.fetchone()
            if not temp_transaction:
                print(f"Transaction ID {trx_id} not found for user {user_id}")
                return jsonify({'status': 'error', 'message': 'Invalid transaction. Please try again.'})

            # Insert into send_money_international
            cursor.execute("""
                INSERT INTO send_money_international (trx_id, account_no, receivers_name, amount_in_bdt, amount_in_selected_country, country, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (trx_id, account_no, receivers_name, amount_in_bdt, amount_in_selected_country, country, user_id))
            print("Transaction inserted into send_money_international table")

            # Deduct balance
            cursor.execute("UPDATE user_profile SET balance = balance - %s WHERE user_id = %s", (amount_in_bdt, user_id))
            print(f"Updated user balance. Deducted {amount_in_bdt} BDT")

            # Notifications and history
            cursor.execute("INSERT INTO notifications (user_id, alerts) VALUES (%s, %s)", 
                           (user_id, f"Sent {amount_in_bdt} BDT internationally to {receivers_name} in {country}"))
            cursor.execute("""
                INSERT INTO history (user_id, type, trx_id, account, amount)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, "International Money Transfer", trx_id, account_no, -amount_in_bdt))
            print("Notification and history added")

            # Clean up temp table
            cursor.execute("DELETE FROM temporary_send_money_international WHERE trx_id = %s", (trx_id,))
            print(f"Deleted temporary transaction {trx_id}")

            db.commit()
            print("Transaction committed successfully")

        return jsonify({'status': 'success', 'message': 'Money sent successfully!'})
    
    except Exception as e:
        db.rollback()
        print(f"Error in confirm_send_money: {str(e)}")
        return jsonify({'status': 'error', 'message': f'An error occurred during transaction: {str(e)}'})



### Ahnaf Ashraf Jameel ###

### Raduan Ahmed Opy ###

### Saifuddin Tanzil ###

### Subah Fatima Hasan ###
