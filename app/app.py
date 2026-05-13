from flask import Flask, jsonify, render_template, request
from pathlib import Path
import pickle
import numpy as np
import yfinance as yf

app = Flask(__name__)

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


@app.route("/")
def home():
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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
