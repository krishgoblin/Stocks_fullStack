import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    user_id = session["user_id"]

    # Retrieve user's transactions (stocks owned) from the database
    transactions_db = db.execute("SELECT symbol, SUM(shares) AS total_shares FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)

    # Initialize variables to store total value of stocks and grand total
    total_stocks_value = 0
    grand_total = 0

    # Iterate through each transaction to calculate total value for each stock
    for transaction in transactions_db:
        symbol = transaction["symbol"]
        total_shares = transaction["total_shares"]

        # Lookup current price for the stock
        stock_info = lookup(symbol)
        current_price = stock_info["price"]

        # Calculate total value of the stock
        total_value = total_shares * current_price

        # Update total value of stocks and grand total
        total_stocks_value += total_value
        grand_total += total_value

        # Add current price and total value to the transaction dictionary
        transaction["current_price"] = current_price
        transaction["total_value"] = total_value

    # Retrieve user's cash balance from the database
    user_db = db.execute("SELECT cash, username FROM users WHERE id = ?", user_id)
    cash_balance = user_db[0]["cash"]
    username = user_db[0]["username"]

    # Calculate grand total (stocks' total value plus cash)
    grand_total += cash_balance

    return render_template("portfolio.html", transactions=transactions_db, cash=cash_balance, username=username, grand_total=grand_total, total_stocks_value = total_stocks_value)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")

    elif request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        try:
            if not symbol:
                return apology("Enter a symbol")

            if not shares:
                return apology("Enter number of shares")

            if shares < 0:
                return apology("Enter valid number of shares")

            stock = lookup(symbol)
            if stock == None:
                return apology("Symbol not available")

            transaction_value = shares * stock["price"]
            user_id = session["user_id"]
            user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
            user_cash = user_cash_db[0]["cash"]

            if user_cash < transaction_value:
                return apology("Not enough money")

            updt_cash = user_cash - transaction_value
            db.execute("UPDATE users SET cash = ? WHERE id = ?", updt_cash, user_id)
            type = "Buy"

            date = datetime.datetime.now()
            db.execute("INSERT INTO transactions(user_id, symbol, shares, price, date, type) VALUES(?, ?, ?, ?, ?, ?)",user_id, stock["symbol"], shares, stock["price"], date, type)

            flash("Bought!")
            return redirect("/")
        except Exception as e:
            return apology("Some error dude to unexpected reasons")


@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]
    trans_db = db.execute("SELECT * FROM transactions WHERE user_id = ?", user_id)
    return render_template("history.html", transactions = trans_db)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")

    elif request.method == "POST":
        symbol = request.form.get("symbol")

        try:
            if not symbol:
                return apology("Enter a symbol")

            stock = lookup(symbol.upper())

            if stock == None:
                return apology("Symbol does not exist")

            return render_template("quoted.html", symbol = stock["symbol"], price = stock["price"])
        except Exception as e:
            return("Error occured due to unexcepted reasons")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    elif request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmPassword = request.form.get("confirmation")

        if not username:
            return apology("Invalid username")

        if not password:
            return apology("Enter Password")

        if not confirmPassword:
            return apology("Re-enter password")

        if password != confirmPassword:
            return apology("Password does not match")

        key = generate_password_hash(password)

        try:
           newUser = db.execute("INSERT INTO users(username, hash) VALUES(?, ?)", username, key)
        except:
            return apology("User already exists")

        session["user_id"] = newUser

        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        user_id = session["user_id"]
        current_symbols = db.execute("SELECT DISTINCT symbol FROM transactions WHERE user_id = ?", user_id)
        return render_template("sell.html", symbols = current_symbols)

    elif request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        if not symbol:
            return apology("Enter a symbol")

        if not shares:
            return apology("Enter number of shares")

        if shares < 0:
            return apology("Enter valid number of shares")

        stock = lookup(symbol)
        if stock == None:
            return apology("Entered incorrect symbol")

        transaction_value = shares * stock["price"]
        user_id = session["user_id"]
        current_shares = db.execute("SELECT SUM(shares) AS shares FROM transactions WHERE symbol = ?", symbol)
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]
        curr_shares = current_shares[0]["shares"]

        if curr_shares < shares:
            return apology("You do not have enough shares")

        updt_shares = curr_shares - shares
        updt_cash = user_cash + transaction_value
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updt_cash, user_id)
        type = "Sold"

        date = datetime.datetime.now()
        db.execute("INSERT INTO transactions(user_id, symbol, shares, price, date, type) VALUES(?, ?, ?, ?, ?, ?)",user_id, stock["symbol"], updt_shares, stock["price"], date, type)

        flash("Sold!")
        return redirect("/")


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "GET":
        return render_template("deposit.html")

    elif request.method == "POST":
        user_id = session["user_id"]
        amount = request.form.get("amount")

        # Fetching cash amount from the database
        cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        cash = int(cash_db[0]["cash"])  # Parsing cash amount to integer

        # Adding deposited amount to the current cash amount
        updt_cash = int(amount) + cash

        # Updating the cash amount in the database
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updt_cash, user_id)  # Passing values as a tuple
        flash("Sccuessfully added funds")
        return redirect("/")
