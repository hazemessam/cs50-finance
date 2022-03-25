import os
from datetime import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


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
    """Show portfolio of stocks"""
    
    stocks = []
    
    user_id = session.get("user_id")
    rows = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    user_cash = rows[0].get("cash")
    grand_total = user_cash
    
    rows = db.execute("SELECT symbol, shares FROM stocks WHERE user_id = ? AND shares > 0", user_id)
    for row in rows:
        stock = lookup(row.get("symbol"))
        shares_value = stock.get("price") * row.get("shares")
        grand_total += shares_value
        grand_total = grand_total
 
        stocks.append({"symbol": row.get("symbol"), "shares": row.get("shares"), "price": stock.get("price"), "shares_value": shares_value})

    return render_template("index.html", stocks=stocks, cash=user_cash, grand_total=grand_total, usd=usd)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares", type=int)

        if not symbol:
            flash("Please, Enter a symbol.", "alert-danger")
            return apology("Please, Enter a symbol.")

        stock = lookup(symbol)
        if not stock:
            flash(f"{symbol} doesn't exist.", "alert-danger")
            return apology(f"{symbol} doesn't exist.")

        symbol = stock.get("symbol")

        if not shares or shares < 1 or shares % 1 != 0:
            flash("Number of shares must be an intger greater than 1.", "alert-danger")
            return apology("Number of shares must be an intger greater than 1.")

        user_id = session.get("user_id")
        rows = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = rows[0].get("cash")
        stock_price = stock.get("price")
        shares_price = stock_price * shares

        if user_cash <  shares_price:
            flash("You don't have enough money.", "alert-danger")
            return apology("You don't have enough money.")

        db.execute("BEGIN TRANSACTION")
        
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", shares_price, user_id)

        created_at = datetime.now()
        created_at =  created_at.strftime("%Y-%m-%d %H:%M:%S")
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, created_at, type) VALUES (?, ?, ?, ?, ?, 'buying')", user_id, symbol, shares, stock_price, created_at)
        
        rows = db.execute("SELECT shares FROM stocks WHERE user_id = ? AND symbol = ?", user_id, symbol)
        if len(rows) == 0:
            db.execute("INSERT INTO stocks (user_id, symbol, shares) VALUES (?, ?, ?)", user_id, symbol, shares)
        else:
            print(user_id, symbol, shares)
            db.execute("UPDATE stocks SET shares = shares + ? WHERE user_id = ? AND symbol = ?", shares, user_id, symbol)

        db.execute("COMMIT")
        
        return redirect('/')

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    
    user_id = session.get("user_id")
    rows = db.execute("SELECT type, symbol, shares, price, created_at FROM transactions WHERE user_id = ?", user_id)
    
    return render_template("history.html", transactions=rows, usd=usd)


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
    
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            flash("Please, enter an symbol.", "alert-danger")
            return apology("Please, enter an symbol.")
        
        stock = lookup(symbol)
        if not stock:
            flash(f"{symbol} does't exist.", "alert-danger")
            return apology(f"{symbol} does't exist.")
        
        return render_template("quoted.html", stock=stock, usd=usd)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        
        if not username:
            return apology("Please, enter a username.")
        
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) != 0:
            flash("Username already exist", "alert-danger")
            return apology("username already exists.")
        
        if not password:
            flash("Please, Enter a password", "alert-danger")
            return apology("Please, Enter a password")
        
        if password != confirmation:
            flash("The confirmation not eqal to the password.", "alert-danger")
            return apology("The confirmation not eqal to the password.")
        
        password_hash = generate_password_hash(password)
        id = db.execute("""INSERT INTO users (username, hash) values (?, ?)""", username, password_hash)
        
        session["user_id"] = id
        
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    
    user_id = session.get("user_id")
    rows = db.execute("SELECT symbol FROM stocks WHERE user_id = ? AND shares > 0", user_id)
    symbols = [row.get("symbol") for row in rows]
    
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            flash("Please, choose a stock.", "alert-danger")
            return apology("Please, choose a stock.")
        
        if symbol not in symbols:
            flash("Please, choose a valid stock.", "alert-danger")
            return apology("Please, choose a valid stock.")
        
        shares = request.form.get("shares", type=int)
        if not shares or shares < 1 or shares % 1 != 0:
            flash("Number of shares must be an intger greater than 1.", "alert-danger")
            return apology("Number of shares must be an intger greater than 1.Number of shares must be an intger greater than 1.")
            
        rows = db.execute("SELECT shares FROM stocks WHERE user_id = ? AND symbol = ?", user_id, symbol)
        if shares > rows[0].get("shares"):
            flash("You don't have enough shares.", "alert-danger")
            return apology("You don't have enough shares.")
        
        stock = lookup(symbol)
        price = stock.get("price")
        created_at = datetime.now()
        created_at =  created_at.strftime("%Y-%m-%d %H:%M:%S")
        
        db.execute("BEGIN TRANSACTION")
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, created_at, type) VALUES (?, ?, ?, ?, ?, 'selling')", user_id, symbol, shares, price, created_at)
        db.execute("UPDATE stocks SET shares = shares - ? WHERE user_id = ? AND symbol = ?", shares, user_id, symbol)
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", price, user_id)
        db.execute("COMMIT")

        return redirect('/')    

    else:
        return render_template("sell.html", symbols=symbols)


if __name__ == '__main__':
    app.run(debug=True)
