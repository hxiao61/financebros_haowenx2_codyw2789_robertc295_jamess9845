from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pathlib import Path
import pickle
import numpy as np
import yfinance as yf
import sqlite3
import os
import datetime
import requests

from build_db import (
    get_db_connection,
    init_db_full,
    get_user_id,
    get_user_by_username,
    create_user,
    cache_dataframe,
    get_cached_rows,
    get_watchlist,
    add_to_watchlist,
    remove_from_watchlist,
    get_portfolio,
    upsert_portfolio,
    remove_from_portfolio,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "financebros")


def get_history(ticker: str, period: str = "6mo"):
    df = yf.Ticker(ticker).history(period=period)
    if df.empty:
        raise ValueError(f"No data found for ticker '{ticker}'")
    return df


def get_history_cached(ticker: str, period: str = "6mo"):
    """Check SQLite cache first; fall back to yFinance and write back on miss."""
    import pandas as pd

    period_days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
    days  = period_days.get(period, 180)
    since = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")

    cached = get_cached_rows(ticker, since)
    if cached:
        latest_cached = cached[-1]["date"]
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        if latest_cached >= yesterday:
            df = pd.DataFrame([dict(r) for r in cached])
            df = df.rename(columns={
                "open": "Open", "high": "High", "low": "Low",
                "close": "Close", "volume": "Volume",
            })
            df["date"] = pd.to_datetime(df["date"])
            return df.set_index("date")

    df = get_history(ticker, period=period)
    cache_dataframe(ticker, df)
    return df


def build_features(df):
    core = df[["Open", "Volume"]].to_numpy()
    if len(core) < 5:
        raise ValueError("Not enough data to create features")
    x = np.zeros((1, 8))
    x[0] = [
        core[-5][0], core[-4][0], core[-3][0], core[-2][0],
        core[-5][1], core[-4][1], core[-3][1], core[-2][1],
    ]
    return x


def get_model_for_ticker(ticker):
    path = MODELS_DIR / f"{ticker}.pkl"
    if path.exists():
        with path.open("rb") as f:
            return pickle.load(f), "ticker"
    return default_model, "default"


def rolling_predictions_with_model(df, model):
    core  = df[["Open", "Volume"]].to_numpy()
    dates = list(df.index)
    preds, pred_dates = [], []
    for i in range(4, len(core) - 1):
        window = core[i - 4:i]
        x = np.array([[
            window[0][0], window[1][0], window[2][0], window[3][0],
            window[0][1], window[1][1], window[2][1], window[3][1],
        ]])
        preds.append(float(model.predict(x)[0]))
        pred_dates.append(dates[i + 1].strftime("%Y-%m-%d"))
    return pred_dates, preds


def get_dashboard_context():
    """Returns market summary cards for the dashboard."""
    indices = {
        "S&P 500": "^GSPC",
        "NASDAQ":  "^IXIC",
        "DOW":     "^DJI",
    }
    cards = []
    for name, sym in indices.items():
        try:
            hist       = get_history_cached(sym, period="1mo")
            latest     = float(hist["Close"].iloc[-1])
            prev       = float(hist["Close"].iloc[-2])
            change_pct = round((latest - prev) / prev * 100, 2)
            cards.append({"name": name, "ticker": sym,
                          "price": round(latest, 2), "change_pct": change_pct})
        except Exception:
            cards.append({"name": name, "ticker": sym, "price": None, "change_pct": None})
    return {"market_summary": cards}



# AUTH DECORATOR


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# AUTH ROUTES


@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        try:
            create_user(username, generate_password_hash(password))
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists.", "danger")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = get_user_by_username(username)
        if user and check_password_hash(user["password"], password):
            session["user"] = user["username"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=session["user"], active="dashboard")


@app.route("/dashboard_data")
@login_required
def get_dashboard_data():
    try:
        return jsonify(get_dashboard_context())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/aianalysis")
@login_required
def aianalysis():
    return render_template("ai_analysis.html", user=session["user"], active="aianalysis")

# ---------------------------------------------------------------
# DEMO
# ---------------------------------------------------------------

@app.route("/demo")
@login_required
def demo():
    return render_template("demo.html", user=session["user"], active="demo")

# STOCK DATA
@app.route("/api/stocks/price")
@login_required
def stock_price():
    ticker = request.args.get("ticker")
    ticker = ticker.upper()

    hist = get_history_cached(ticker, period="1mo")
    latest = float(hist["Close"].iloc[-1])
    prev = float(hist["Close"].iloc[-2])
    change_pct = round((latest - prev) / prev * 100, 2)

    return jsonify({
        "ticker": ticker,
        "price": round(latest, 2),
        "change_pct" : change_pct
    })

@app.route("/api/stocks/search")
@login_required
def stock_search():
    query = request.args.get("q")
    query = query.upper()

    stock_info = yf.Ticker(query).info
    name = stock_info.get("longName")
    hist = get_history_cached(query, period="1mo")
    latest = float(hist["Close"].iloc[-1])

    return jsonify({
        "ticker": query,
        "name": name,
        "price": round(latest, 2),
    })


# WATCHLIST


@app.route("/watchlist")
@login_required
def watchlist():
    user_id = get_user_id(session["user"])
    tickers = get_watchlist(user_id)
    items   = []
    for t in tickers:
        try:
            hist       = get_history_cached(t, period="1mo")
            latest     = float(hist["Close"].iloc[-1])
            prev       = float(hist["Close"].iloc[-2])
            change_pct = round((latest - prev) / prev * 100, 2)
            items.append({"ticker": t, "price": round(latest, 2), "change_pct": change_pct})
        except Exception:
            items.append({"ticker": t, "price": None, "change_pct": None})
    return render_template("watchlist.html", user=session["user"],
                           active="watchlist", items=items)


@app.route("/api/watchlist", methods=["GET"])
@login_required
def watchlist_list():
    user_id = get_user_id(session["user"])
    return jsonify({"tickers": get_watchlist(user_id)})


@app.route("/api/watchlist/add", methods=["POST"])
@login_required
def watchlist_add():
    data   = request.get_json(silent=True) or {}
    ticker = str(data.get("ticker", "")).strip().upper()
    if not ticker or not ticker.isalpha() or len(ticker) > 10:
        return jsonify({"error": "Invalid ticker"}), 400
    add_to_watchlist(get_user_id(session["user"]), ticker)
    return jsonify({"status": "added", "ticker": ticker})


@app.route("/api/watchlist/remove", methods=["POST"])
@login_required
def watchlist_remove():
    data   = request.get_json(silent=True) or {}
    ticker = str(data.get("ticker", "")).strip().upper()
    remove_from_watchlist(get_user_id(session["user"]), ticker)
    return jsonify({"status": "removed", "ticker": ticker})



# PORTFOLIO


@app.route("/portfolio")
@login_required
def portfolio():
    user_id  = get_user_id(session["user"])
    rows     = get_portfolio(user_id)
    holdings = []
    total_value, total_cost = 0.0, 0.0

    for r in rows:
        try:
            hist  = get_history_cached(r["ticker"], period="1mo")
            price = float(hist["Close"].iloc[-1])
        except Exception:
            price = None

        cost      = r["shares"] * r["avg_price"]
        mkt_value = r["shares"] * price if price else None
        gain_loss = (mkt_value - cost) if mkt_value is not None else None
        gain_pct  = (gain_loss / cost * 100) if (gain_loss is not None and cost) else None

        if mkt_value:
            total_value += mkt_value
        total_cost += cost

        holdings.append({
            "ticker":    r["ticker"],
            "shares":    r["shares"],
            "avg_price": r["avg_price"],
            "cur_price": round(price, 2)     if price     is not None else None,
            "mkt_value": round(mkt_value, 2) if mkt_value is not None else None,
            "gain_loss": round(gain_loss, 2) if gain_loss is not None else None,
            "gain_pct":  round(gain_pct,  2) if gain_pct  is not None else None,
            "created_at": r["created_at"],
        })

    return render_template(
        "portfolio.html",
        user=session["user"],
        active="portfolio",
        holdings=holdings,
        total_value=round(total_value, 2),
        total_cost=round(total_cost, 2),
        total_gain=round(total_value - total_cost, 2),
    )


@app.route("/api/portfolio/add", methods=["POST"])
@login_required
def portfolio_add():
    data = request.get_json(silent=True) or {}
    ticker    = str(data.get("ticker", "")).strip().upper()
    shares    = data.get("shares")
    avg_price = data.get("avg_price")

    if not ticker or not ticker.isalpha() or len(ticker) > 10:
        return jsonify({"error": "Invalid ticker"}), 400
    try:
        shares    = float(shares)
        avg_price = float(avg_price)
        assert shares > 0 and avg_price > 0
    except Exception:
        return jsonify({"error": "shares and avg_price must be positive numbers"}), 400

    upsert_portfolio(get_user_id(session["user"]), ticker, shares, avg_price)
    return jsonify({"status": "ok", "ticker": ticker})


@app.route("/api/portfolio/remove", methods=["POST"])
@login_required
def portfolio_remove():
    data   = request.get_json(silent=True) or {}
    ticker = str(data.get("ticker", "")).strip().upper()
    remove_from_portfolio(get_user_id(session["user"]), ticker)
    return jsonify({"status": "removed", "ticker": ticker})


init_db_full()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
