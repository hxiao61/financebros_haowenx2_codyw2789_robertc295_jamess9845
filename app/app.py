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
    get_paper_balance,
    set_paper_balance,
    get_paper_holdings,
    paper_buy,
    paper_sell,
    add_paper_transaction,
    get_paper_transactions,
    reset_paper_portfolio,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "financebros")

OPENROUTER_KEY = "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"

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "proto" / "stock_model.pkl"
MODELS_DIR = BASE_DIR / "proto" / "models"
with MODEL_PATH.open("rb") as f:
    default_model = pickle.load(f)

def get_history(ticker: str, period: str = "6mo"):
    df = yf.Ticker(ticker).history(period=period)
    if df.empty:
        raise ValueError(f"No data found for ticker '{ticker}'")
    return df


def get_history_cached(ticker: str, period: str = "6mo"):
    """Check SQLite cache first; fall back to yFinance and write back on miss."""
    import pandas as pd

    period_days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
    days  = period_days.get(period, 180)
    since = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")

    cached = get_cached_rows(ticker, since)
    if cached:
        latest_cached = cached[-1]["date"]
        oldest_cached = cached[0]["date"]
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        if latest_cached >= yesterday and oldest_cached <= since:
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
            hist       = get_latest_history(sym)
            if hist is None:
                cards.append({"name": name, "ticker": sym, "price": None, "change_pct": None})
                continue
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

@app.route("/api/ai", methods=["POST"])
@login_required
def ai_query():
    data = request.get_json(silent=True) or {}
    bigq = str(data.get("question", "")).strip()
    if not bigq:
        return jsonify({"error": "No question provided"}), 400

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
            json={
                "model": "nvidia/nemotron-3-super-120b-a12b:free",
                "messages": [
                    {"role": "system", "content": "You are a concise financial analyst. Answer stock market questions clearly and briefly."},
                    {"role": "user", "content": bigq}
                ]
            },
            timeout=30
        )
        resp.raise_for_status()
        brainResponse = resp.json()["choices"][0]["message"]["content"].strip()

        conn = get_db_connection()
        conn.execute(
            "INSERT OR IGNORE INTO ai_queries (user_id, question, answer, created_at) VALUES (?,?,?,datetime('now'))",
            (get_user_id(session["user"]), bigq, brainResponse)
        )
        conn.commit()
        conn.close()

        return jsonify({"answer": brainResponse})
    except Exception as oopsie:
        return jsonify({"error": str(oopsie)}), 500

@app.route("/stockviewer")
@login_required
def stockviewer():
    return render_template("stock_viewer.html", user=session["user"], active="stockviewer")

@app.route("/forecast")
@login_required
def forecast():
    return render_template("forecast.html", user=session["user"], active="forecast")

@app.route("/stock/<ticker>")
@login_required
def stock_detail(ticker):
    return render_template("stock_detail.html", user=session["user"], ticker=ticker.upper())

@app.route("/api/model/check")
@login_required
def chk_pkl():
    stonk = request.args.get("ticker", "").upper()
    pkl_exists = (MODELS_DIR / f"{stonk}.pkl").exists()
    return jsonify({"ticker": stonk, "has_model": pkl_exists})

@app.route("/api/retrain", methods=["POST"])
@login_required
def retrain_brrr():
    import subprocess, sys
    yolo = request.get_json(silent=True) or {}
    stonk = str(yolo.get("ticker", "")).upper()
    if not stonk:
        return jsonify({"error": "no ticker"}), 400
    try:
        train_script = BASE_DIR / "proto" / "train_ticker_models.py"
        bigbrain = subprocess.run(
            [sys.executable, str(train_script)],
            capture_output=True, text=True, timeout=120
        )
        pkl_ready = (MODELS_DIR / f"{stonk}.pkl").exists()
        return jsonify({"done": True, "ticker": stonk, "has_model": pkl_ready})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "training timed out"}), 500
    except Exception as oops:
        return jsonify({"error": str(oops)}), 500

# ---------------------------------------------------------------
# DEMO
# ---------------------------------------------------------------

@app.route("/api/predict", methods=["POST"])
@login_required
def predict():
    data = request.get_json(silent=True) or {}
    ticker = str(data.get("ticker", "NVDA")).strip().upper()

    try:
        model, model_source = get_model_for_ticker(ticker)
        history = get_history_cached(ticker, period="6mo")
        x = build_features(history)
        predicted_open = float(model.predict(x)[0])

        opens = history["Open"]
        labels = []
        actual = []
        for date in opens.index:
            labels.append(date.strftime("%Y-%m-%d"))
            actual.append(float(opens[date]))

        rolling_labels, rolling_preds = rolling_predictions_with_model(history, model)
        rolling_map = {}
        for i in range(len(rolling_labels)):
            rolling_map[rolling_labels[i]] = rolling_preds[i]

        rolling_series = []
        for label in labels:
            if label in rolling_map:
                rolling_series.append(rolling_map[label])
            else:
                rolling_series.append(None)

        last_open = float(history["Open"].iloc[-1])
        delta = predicted_open - last_open
        if last_open != 0:
            delta_pct = (delta / last_open) * 100
        else:
            delta_pct = 0.0

        prediction_line = [None] * len(actual)
        prediction_line.append(predicted_open)

        labels.append("Next Day (Pred)")
        actual.append(None)
        rolling_series.append(None)

        return jsonify({
            "ticker": ticker,
            "labels": labels,
            "actual": actual,
            "rolling_prediction": rolling_series,
            "prediction": prediction_line,
            "predicted_open": round(predicted_open, 4),
            "last_open": round(last_open, 4),
            "delta": round(delta, 4),
            "delta_pct": round(delta_pct, 4),
            "model_source": model_source,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# STOCK DATA
@app.route("/api/stocks/price")
@login_required
def stock_price():
    ticker = request.args.get("ticker")
    ticker = ticker.upper()

    try:
        fi = yf.Ticker(ticker).fast_info
        price = fi.last_price
        prev_close = fi.previous_close

        if price is None:
            raise ValueError("no price")

        change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else None

        return jsonify({
            "ticker":     ticker,
            "price":      round(price, 2),
            "change_pct": change_pct,
            "open":       round(fi.open, 2)        if fi.open       else None,
            "high":       round(fi.day_high, 2)    if fi.day_high   else None,
            "low":        round(fi.day_low, 2)     if fi.day_low    else None,
            "volume":     int(fi.last_volume)      if fi.last_volume else None,
        })
    except Exception:
        return jsonify({
            "ticker": ticker,
            "price": None, "change_pct": None,
            "open": None, "high": None, "low": None, "volume": None,
        })


@app.route("/api/stocks/search")
@login_required
def stock_search():
    query = request.args.get("q")
    query = query.upper()

    stock_info = yf.Ticker(query).info
    name = stock_info.get("longName")
    hist = get_latest_history(query)

    if hist is None:
        return jsonify({
            "ticker": query,
            "name": name,
            "price": None,
        })

    latest = float(hist["Close"].iloc[-1])

    return jsonify({
        "ticker": query,
        "name": name,
        "price": round(latest, 2),
    })

@app.route("/api/stocks/history")
@login_required
def stock_history():
    ticker = request.args.get("ticker", "AAPL").upper()
    period = request.args.get("period", "6mo")
    try:
        df = get_history_cached(ticker, period=period)
        prices = [round(float(p), 2) for p in df["Close"].tolist()]
        labels = [d.strftime("%Y-%m-%d") for d in df.index]
        return jsonify({
            "ticker": ticker,
            "prices": prices,
            "labels": labels,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/stocks/modal_data")
@login_required
def stonk_modal_data():
    import pandas as pd
    stonk = request.args.get("ticker", "AAPL").upper()
    try:
        dat = get_history_cached(stonk, period="1y")
    except Exception as oops:
        return jsonify({"error": f"no data for {stonk}: {str(oops)}"}), 400

    try:
        import math
        dates_bro = [d.strftime("%Y-%m-%d") for d in dat.index]
        closes_bro = [round(float(p), 2) for p in dat["Close"].tolist()]

        # Resample monthly
        monthly_stonk = dat.resample("ME").last()
        m_lbls = monthly_stonk.index.strftime("%b %Y").tolist()

        if not monthly_stonk.empty:
            base_price = monthly_stonk["Close"].iloc[0]
            stonk_gainz = ((monthly_stonk["Close"] / base_price) * 100).round(2).tolist()
        else:
            stonk_gainz = []

        monthly_vol_dat = dat.resample("ME").mean(numeric_only=True)
        big_vol = monthly_vol_dat["Volume"].round(2).tolist() if not monthly_vol_dat.empty else []

        # Sharpe (2y)
        faang_gang = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA"]
        if stonk not in faang_gang:
            faang_gang.append(stonk)

        sharpe_list = []
        for f_stonk in faang_gang:
            try:
                df_f = get_history_cached(f_stonk, period="2y")
                closes = df_f["Close"]
                pct_chg = closes.pct_change().dropna()
                avg_chg = pct_chg.mean() * 252
                vol = pct_chg.std() * np.sqrt(252)
                sharpe_score = (avg_chg - 0.037) / vol if vol > 0 else 0

                if math.isnan(sharpe_score) or math.isnan(avg_chg) or math.isnan(vol):
                    continue
                sharpe_list.append({
                    "ticker": f_stonk,
                    "sharpe_ratio": round(sharpe_score, 3),
                    "annual_return": round(avg_chg * 100, 2),
                    "annual_volatility": round(vol * 100, 2),
                })
            except Exception:
                continue

        sharpe_list.sort(key=lambda x: x["sharpe_ratio"], reverse=True)

        # Indexed growth comparison
        compare_gainz = []
        seen_tickers = set()
        for f_stonk in ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", stonk]:
            if f_stonk in seen_tickers:
                continue
            seen_tickers.add(f_stonk)
            try:
                df_f = get_history_cached(f_stonk, period="1y")
                m_df = df_f.resample("ME").last()
                if not m_df.empty:
                    b_price = m_df["Close"].iloc[0]
                    indexed = ((m_df["Close"] / b_price) * 100).round(2).tolist()
                    compare_gainz.append({
                        "ticker": f_stonk,
                        "data": indexed
                    })
            except Exception:
                continue

        swag_bag = {
            "ticker": stonk,
            "price_labels": dates_bro,
            "price_closes": closes_bro,
            "monthly_labels": m_lbls,
            "ticker_growth": stonk_gainz,
            "monthly_volume": big_vol,
            "sharpe_data": sharpe_list,
            "growth_datasets": compare_gainz
        }
        return jsonify(swag_bag)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stocks/info")
@login_required
def stock_info():
    from datetime import datetime
    ticker = request.args.get("ticker", "").upper()
    try:
        info = yf.Ticker(ticker).info

        def fmt_big(v):
            if v is None: return None
            if v >= 1e12: return f"${v/1e12:.2f}T"
            if v >= 1e9:  return f"${v/1e9:.2f}B"
            if v >= 1e6:  return f"${v/1e6:.2f}M"
            return f"${v:,.0f}"

        def pct(v):
            return round(v * 100, 2) if v is not None else None

        def r2(v):
            return round(v, 2) if v is not None else None

        ex_div = info.get("exDividendDate")
        ex_div_str = datetime.fromtimestamp(ex_div).strftime("%Y-%m-%d") if ex_div else None

        ev = info.get("enterpriseValue")
        ebitda = info.get("ebitda")

        return jsonify({
            # identity
            "name":             info.get("longName"),
            "sector":           info.get("sector"),
            "industry":         info.get("industry"),
            "website":          info.get("website"),
            "employees":        info.get("fullTimeEmployees"),
            # valuation
            "market_cap":       fmt_big(info.get("marketCap")),
            "enterprise_value": fmt_big(ev),
            "pe_trailing":      r2(info.get("trailingPE")),
            "pe_forward":       r2(info.get("forwardPE")),
            "peg_ratio":        r2(info.get("pegRatio")),
            "price_book":       r2(info.get("priceToBook")),
            "price_sales":      r2(info.get("priceToSalesTrailing12Months")),
            "ev_ebitda":        r2(ev / ebitda) if ev and ebitda else None,
            # financials
            "revenue":          fmt_big(info.get("totalRevenue")),
            "net_income":       fmt_big(info.get("netIncomeToCommon")),
            "ebitda":           fmt_big(ebitda),
            "free_cash_flow":   fmt_big(info.get("freeCashflow")),
            "eps_trailing":     r2(info.get("trailingEps")),
            "eps_forward":      r2(info.get("forwardEps")),
            "profit_margin":    pct(info.get("profitMargins")),
            "operating_margin": pct(info.get("operatingMargins")),
            "gross_margin":     pct(info.get("grossMargins")),
            "roe":              pct(info.get("returnOnEquity")),
            "roa":              pct(info.get("returnOnAssets")),
            "debt_equity":      r2(info.get("debtToEquity")),
            # dividends
            "dividend_yield":   pct(info.get("dividendYield")),
            "dividend_rate":    r2(info.get("dividendRate")),
            "payout_ratio":     pct(info.get("payoutRatio")),
            "ex_div_date":      ex_div_str,
            # analyst
            "analyst_rating":   info.get("recommendationKey"),
            "analyst_target":   r2(info.get("targetMeanPrice")),
            "analyst_count":    info.get("numberOfAnalystOpinions"),
            # technical
            "week52_high":      r2(info.get("fiftyTwoWeekHigh")),
            "week52_low":       r2(info.get("fiftyTwoWeekLow")),
            "beta":             r2(info.get("beta")),
            "short_float":      pct(info.get("shortPercentOfFloat")),
            "avg_volume":       info.get("averageVolume"),
            # ownership
            "insider_pct":      pct(info.get("heldPercentInsiders")),
            "inst_pct":         pct(info.get("heldPercentInstitutions")),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


def get_latest_history(ticker: str):
    hist = yf.Ticker(ticker).history(period="1d", interval="2m")
    if not hist.empty and len(hist) >= 2:
        return hist
    month_hist = get_history_cached(ticker, period="1mo")
    if not month_hist.empty and len(month_hist)>= 2:
        return month_hist
    return None
        
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
            hist = get_latest_history(r["ticker"])
            if hist is None:
                price = None
            else:
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

# ---------------------------------------------------------------
# PAPER TRADING
# ---------------------------------------------------------------

@app.route("/paper")
@login_required
def paper_trading():
    return render_template("paper_trading.html", user=session["user"], active="paper")


@app.route("/api/paper/state")
@login_required
def paper_state():
    user_id = get_user_id(session["user"])
    cash = get_paper_balance(user_id)
    raw_holdings = get_paper_holdings(user_id)
    raw_txns = get_paper_transactions(user_id, limit=50)

    holdings = []
    total_mkt = 0.0
    total_cost = 0.0
    for h in raw_holdings:
        try:
            fi = yf.Ticker(h["ticker"]).fast_info
            price = fi.last_price
        except Exception:
            price = None

        cost = h["shares"] * h["avg_cost"]
        mkt = h["shares"] * price if price is not None else None
        gl = (mkt - cost) if mkt is not None else None
        gl_pct = (gl / cost * 100) if (gl is not None and cost) else None

        if mkt:
            total_mkt += mkt
        total_cost += cost

        holdings.append({
            "ticker":    h["ticker"],
            "shares":    h["shares"],
            "avg_cost":  round(h["avg_cost"], 4),
            "cur_price": round(price, 2) if price is not None else None,
            "mkt_value": round(mkt, 2) if mkt is not None else None,
            "gain_loss": round(gl, 2) if gl is not None else None,
            "gain_pct":  round(gl_pct, 2) if gl_pct is not None else None,
        })

    transactions = [
        {
            "ticker":     t["ticker"],
            "action":     t["action"],
            "shares":     t["shares"],
            "price":      t["price"],
            "total":      t["total"],
            "created_at": t["created_at"],
        }
        for t in raw_txns
    ]

    total_equity = cash + total_mkt
    total_gl = total_equity - (100000.0)

    return jsonify({
        "cash":         round(cash, 2),
        "holdings":     holdings,
        "transactions": transactions,
        "total_mkt":    round(total_mkt, 2),
        "total_equity": round(total_equity, 2),
        "total_gl":     round(total_gl, 2),
        "total_gl_pct": round(total_gl / 100000.0 * 100, 2),
    })


@app.route("/api/paper/buy", methods=["POST"])
@login_required
def paper_trade_buy():
    data = request.get_json(silent=True) or {}
    ticker = str(data.get("ticker", "")).strip().upper()
    shares = data.get("shares")

    if not ticker or not ticker.replace(".", "").isalnum() or len(ticker) > 10:
        return jsonify({"error": "Invalid ticker"}), 400
    try:
        shares = float(shares)
        assert shares > 0
    except Exception:
        return jsonify({"error": "shares must be a positive number"}), 400

    try:
        fi = yf.Ticker(ticker).fast_info
        price = fi.last_price
        if price is None:
            raise ValueError("no price")
        price = float(price)
    except Exception:
        return jsonify({"error": f"Could not get price for {ticker}"}), 400

    total = shares * price
    user_id = get_user_id(session["user"])
    cash = get_paper_balance(user_id)

    if total > cash:
        return jsonify({"error": f"Insufficient funds — need ${total:,.2f}, have ${cash:,.2f}"}), 400

    set_paper_balance(user_id, cash - total)
    paper_buy(user_id, ticker, shares, price)
    add_paper_transaction(user_id, ticker, "BUY", shares, price, total)

    return jsonify({
        "status": "ok",
        "ticker": ticker,
        "shares": shares,
        "price":  round(price, 4),
        "total":  round(total, 2),
        "cash":   round(cash - total, 2),
    })


@app.route("/api/paper/sell", methods=["POST"])
@login_required
def paper_trade_sell():
    data = request.get_json(silent=True) or {}
    ticker = str(data.get("ticker", "")).strip().upper()
    shares = data.get("shares")

    if not ticker or not ticker.replace(".", "").isalnum() or len(ticker) > 10:
        return jsonify({"error": "Invalid ticker"}), 400
    try:
        shares = float(shares)
        assert shares > 0
    except Exception:
        return jsonify({"error": "shares must be a positive number"}), 400

    try:
        fi = yf.Ticker(ticker).fast_info
        price = fi.last_price
        if price is None:
            raise ValueError("no price")
        price = float(price)
    except Exception:
        return jsonify({"error": f"Could not get price for {ticker}"}), 400

    user_id = get_user_id(session["user"])
    ok = paper_sell(user_id, ticker, shares)
    if not ok:
        return jsonify({"error": f"Not enough shares of {ticker}"}), 400

    total = shares * price
    cash = get_paper_balance(user_id)
    set_paper_balance(user_id, cash + total)
    add_paper_transaction(user_id, ticker, "SELL", shares, price, total)

    return jsonify({
        "status": "ok",
        "ticker": ticker,
        "shares": shares,
        "price":  round(price, 4),
        "total":  round(total, 2),
        "cash":   round(cash + total, 2),
    })


@app.route("/api/paper/reset", methods=["POST"])
@login_required
def paper_reset():
    user_id = get_user_id(session["user"])
    reset_paper_portfolio(user_id)
    return jsonify({"status": "reset", "cash": 100000.0})


init_db_full()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=True)
