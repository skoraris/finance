import os
import sqlite3
#from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = sqlite3.connect("finance.db")
# Προσθέτω νέους πίνακες στη βάση

db.execute("CREATE TABLE IF NOT EXISTS History (user_id INTEGER, Symbol TEXT,Name TEXT, B_S TEXT,Number INTEGER, Price TEXT,\
Date TEXT, Balance TEXT)")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    symbol = db.execute("SELECT Symbol, SUM(CASE B_S WHEN ? THEN Number When ? THEN - Number END) AS total_shares,\
    Name, cash FROM History JOIN users ON users.id = History.user_id\
    WHERE user_id=? AND B_S NOT NULL GROUP BY Symbol;",  'B', 'S', session.get("user_id"))

    if not symbol:  # έστω και μια κενή ή None θέση να συναντήσει επιστρέφει άδεια λίστα (flask documentation)
        symbol.append({'Symbol': 'None', 'total_shares': 0, 'Name': 'None', 'cash': 10000, 'price': 0})
        return render_template("/index.html", symbol=symbol)
    for company in symbol:
        company['price'] = lookup(company['Symbol'])['price']
    return render_template("/index.html", symbol=symbol)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == 'POST':
        if not request.form.get("symbol"):
            return apology("Please type a valid symbol")
        company = request.form.get("symbol")
        value = lookup(company)
        if value == None:
            return apology("Please type a valid symbol")
        shares = request.form.get("shares")
        if shares.isdigit() and int(shares) >= 1:
            user_id = session.get("user_id")
            # Το session["user_id"] δε δουλεύει γιατί μάλλον έχει αποθηκευμένα στο λεξικό session το id του ενεργού loged_in λογαριασμού
            balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
            # ή db.execute (f"SELECT cash FROM users WHERE id = {user_id}")
            if int(shares)*value['price'] > balance[0].get("cash"):
                # Συγκρίνω κόστος αγοράς με υπόλοιπο λογαριασμού όπου balance ειναι της μορφής [{'cash': 10000}]
                return apology('Sorry but your balance is not enough to proceed')
            date = datetime.now().strftime("%B %d, %Y %I:%M%p")
            db.execute("INSERT INTO History(user_id, Symbol,Name, B_S, Number, Price, Date, Balance) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                       user_id, company, value['name'], 'B', shares, value['price'], date, balance[0].get("cash") - int(shares)*value['price'])
            db.execute("UPDATE users SET cash = ? WHERE id = ? ", balance[0].get("cash") - int(shares)*value['price'], user_id)
            flash("Transaction Complete!")
            # προσοχή!! στην index.html δε βάζουμε τον κώδικα που απαιτεί στο documentation του flash  γιατί υπάρχει στο layout.html από τη bootstrap ήδη!
            return redirect("/")
            # ("/" και όχι "/index" διότι αυτό είναι το route πανω από την def index. Αλλιώς με url_for("/index") που οδηγεί απευθείας στο route της συνάρτησης def index)
        else:
            return apology("You have to type a number of shares greater or equal to 1")
    return render_template("/buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session.get("user_id")
    history = db.execute("SELECT Symbol, Number, B_S, Price, Date FROM History WHERE user_id = ?", user_id)
    if len(history) == 1:
        # Όσοι είναι register έχουν μια Null συναλλαγή που περνάω κατά την εγγραφή τους
        flash('No transactions yet')
        # άρα αν έχουν μόνο μία συναλλαγή πρακτικά δεν έχουν καμία
        return render_template("/history.html")
    for transaction in history:
        if transaction['Symbol'] == None:
            # Αφαιρώ τη συναλλάγη με None την οποία καταχώρησα κατά το register
            history.remove(transaction)
        if transaction['B_S'] == 'S':
            transaction['Number'] = - transaction['Number']
        transaction['Price'] = float(transaction['Price'])
    history[0]['Price'] = float(history[0]['Price'])
    # το μετατρέπω ξεχωριστά γιατί (ΔΕΝ ΜΠΟΡΩ ΝΑ ΚΑΤΑΛΑΒΩ ΓΙΑΤΙ!)
# στην παραπάνω for δεν το μετατρέπει!!
    return render_template("/history.html", history=history)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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
    """Get stock quote."""
    if request.method == 'POST':
        if not request.form.get("symbol"):
            return apology("Please type a valid symbol")
        company = request.form.get("symbol")
        value = lookup(company)
        if value == None:
            return apology("Please type a valid symbol")
        return render_template("/quoted.html", value=value)
    return render_template("/quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        namelist = []
        # Λίστα όπου αποθηκεύω προσωρινά όλα τα usernames απο τη βάση δεδομένων για να συγκρίνω με αυτό που πληκτρολογεί ο χρήστης όταν κάνει register
        username = request.form.get("username")
        if len(request.form.get("password")) < 5:
            return apology("Your password must be at least 5 characters long")
        find = False
        for char in ['!', '@', '#', '$', '%', '^', '&', '*', '?']:
            if char in request.form.get("password"):
                find = True
                break
        if find == False:
            return apology("Your password must contain at least one of the '!','@','#','$','%','^','&','*','?'")
        password = generate_password_hash(request.form.get("password"))
        users = db.execute("SELECT username FROM users")
        # επιλέγω τα username αλλά το αποτέλεσμα είναι λεξικά τύπου {'username':'nikolas' ,'username':'galis'}Κλπ
        for name in users:
            # Βάζω σε μία λίστα μόνο τα usernames για να τσεκάρω αν κάποιο username χρησιμοποιείται ήδη
            namelist.append(name['username'])
        if not request.form.get("username") or username in namelist:
            return apology("Must provide username or username is allready taken")
        elif not request.form.get("password"):
            return apology("Must provide password")
        elif not request.form.get("confirmation") or request.form.get("confirmation") != request.form.get("password"):
            return apology("Must confirm your password or your password dont mutch")
        else:
            db.execute("INSERT INTO users (username, hash, Registration_Date) VALUES(?, ?, ?)",
                       username, password, datetime.now().strftime("%B %d, %Y %I:%M%p"))
            db.execute("INSERT INTO History (user_id, Balance, Number, Price) SELECT users.id, users.cash, 0, 0 \
            FROM users WHERE username = ?", username)
            return redirect("/login")
    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == 'POST':
        if not request.form.get("symbol"):
            return apology("Please select a share to sell")
        company = request.form.get("symbol")
        value = lookup(company)
        if value == None:
            return apology("Please select a share to sell")
        shares = request.form.get("shares")
        user_id = session.get("user_id")
        # Το session["user_id"] δε δουλεύει γιατί μάλλον έχει αποθηκευμένα στο λεξικό session το id του ενεργού loged_in λογαριασμού
        balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        # ή db.execute (f"SELECT cash FROM users WHERE id = {user_id}")
        date = datetime.now().strftime("%B %d, %Y %I:%M%p")
        shares_own = db.execute("SELECT SUM(CASE B_S WHEN ? THEN Number WHEN ? THEN - Number END) AS shares_own\
        FROM History JOIN users ON History.user_id = users.id WHERE users.id = ? AND Symbol = ?", 'B', 'S', user_id, value['symbol'])
        if shares_own[0]['shares_own'] < int(shares):
            return apology(f"Sorry you have less shares from  {value['name']} in your portfolio")
        db.execute("INSERT INTO History(user_id, Symbol,Name, B_S, Number, Price, Date, Balance)\
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)", user_id, company, value['name'], 'S', shares, value['price'], date, balance[0].get("cash") + int(shares)*value['price'])
        db.execute("UPDATE users SET cash = ? WHERE id = ? ", balance[0].get("cash") + int(shares)*value['price'], user_id)
        flash("Transaction Complete!")
        # προσοχή!! στην index.html δε βάζουμε τον κώδικα που απαιτεί στο documentation του flash  γιατί υπάρχει στο layout.html από τη bootstrap ήδη!

        return redirect("/")
        # ("/" και όχι "/index" διότι αυτό είναι το route πανω από την def index. Αλλιώς με url_for("/index") που οδηγεί απευθείας στο route της συνάρτησης def index

    shares_own = db.execute("SELECT Symbol, SUM(CASE B_S WHEN ? THEN Number WHEN ? THEN - Number END)\
    AS total_shares FROM History JOIN users ON users.id = History.user_id WHERE user_id=? GROUP BY Symbol;", 'B', 'S', session.get("user_id"))
    for own in shares_own:
        if own['Symbol'] == None:
            # Αφαιρώ τη συναλλάγη με None την οποία καταχώρησα κατά το register
            shares_own.remove(own)
    return render_template("/sell.html", shares_own=shares_own)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


@app.route("/Myaccount", methods=["GET", "POST"])
@login_required
def Myaccount():
    """Personal info and change passwd"""
    user_id = session.get("user_id")
    personal = db.execute("SELECT Username, Registration_Date, hash  FROM users WHERE id = ?", user_id)
    if request.method == 'POST':
        oldpassword = request.form.get("oldpasswd")
        if not request.form.get("oldpasswd") or not request.form.get("newpasswd") or not request.form.get("retype"):
            return apology("Please fill all the required fields")
        if not check_password_hash(personal[0]["hash"], request.form.get("oldpasswd")):
            return apology("Incorrect password!!")
        find = False
        for char in ['!', '@', '#', '$', '%', '^', '&', '*', '?']:
            if char in request.form.get("newpasswd"):
                find = True
                break
        if find == False:
            return apology("Your password must contain at least one of the '!','@','#','$','%','^','&','*','?' ")
        if len(request.form.get("newpasswd")) < 5:
            return apology("Your password must be at least 5 characters long")
        if request.form.get("newpasswd") != request.form.get("retype"):
            return apology("Passwords dont match!")
        db.execute("UPDATE users SET hash = ? WHERE id = ? ", generate_password_hash(request.form.get("newpasswd")), user_id)
        flash("Password changed!")
        return redirect("/Myaccount")
        # redirect για να ξαναδιαβάσει και τη συνάρτηση
    return render_template("/Myaccount.html", personal=personal)
