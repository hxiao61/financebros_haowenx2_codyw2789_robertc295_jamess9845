from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pathlib import Path
import pickle
import numpy as np
import yfinance as yf
import sqlite3

DATABASE = "users.db"

app = Flask(__name__)
app.secret_key = "financebros"

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
    core = df[["Open", "Volume"]].to_numpy()
    dates = list(df.index)
    preds = []
    pred_dates = []
    for i in range(4, len(core) - 1):
        window = core[i - 4:i]
        x = np.array(
            [[
                window[0][0], window[1][0], window[2][0], window[3][0],
                window[0][1], window[1][1], window[2][1], window[3][1],
            ]]
        )
        pred = float(model.predict(x)[0])
        preds.append(pred)
        pred_dates.append(dates[i + 1].strftime("%Y-%m-%d"))
    return pred_dates, preds


@app.route("/demo")
def demo():
    return render_template("demo.html")


@app.route("/api/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True) or {}
    ticker = str(data.get("ticker", "NVDA")).strip().upper()
    try:
        model, model_source = get_model_for_ticker(ticker)
        history = get_history(ticker, period="6mo")
        x = build_features(history)
        predicted_open = float(model.predict(x)[0])
        opens = history["Open"]
        labels = [idx.strftime("%Y-%m-%d") for idx in opens.index]
        actual = [float(v) for v in opens.values]
        rolling_labels, rolling_preds = rolling_predictions_with_model(history, model)
        rolling_map = dict(zip(rolling_labels, rolling_preds))
        rolling_series = [rolling_map.get(label) for label in labels]
        next_label = "Next Day (Pred)"
        last_open = float(history["Open"].iloc[-1])
        delta = predicted_open - last_open
        delta_pct = (delta / last_open) * 100 if last_open else 0.0
        return jsonify(
            {
                "ticker": ticker,
                "labels": labels + [next_label],
                "actual": actual + [None],
                "rolling_prediction": rolling_series + [None],
                "prediction": [None] * len(actual) + [predicted_open],
                "predicted_open": round(predicted_open, 4),
                "last_open": round(last_open, 4),
                "delta": round(delta, 4),
                "delta_pct": round(delta_pct, 4),
                "model_source": model_source,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
#---------------------
#login stuff

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_db()

# app routes
@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password),
            )
            conn.commit()
            conn.close()

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

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user"] = user["username"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=session["user"])


@app.route("/dashboard_data")
@login_required
def get_dashboard_data():
    try:
        return jsonify(get_dashboard_context())
    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
