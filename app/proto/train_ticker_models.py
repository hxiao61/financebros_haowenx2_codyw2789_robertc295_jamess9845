from pathlib import Path
import pickle
import numpy as np
import yfinance as yf
from sklearn.ensemble import RandomForestRegressor

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA"]
BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "models"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def build_xy(df):
    core = df[["Open", "Volume"]].to_numpy()
    x = []
    y = []
    for i in range(4, len(core) - 1):
        w = core[i - 4:i]
        x.append([
            w[0][0], w[1][0], w[2][0], w[3][0],
            w[0][1], w[1][1], w[2][1], w[3][1],
        ])
        y.append(core[i + 1][0])
    return np.array(x), np.array(y)


def train_one(ticker):
    df = yf.Ticker(ticker).history(period="5y")
    if df.empty or len(df) < 80:
        raise ValueError(f"Not enough data for {ticker}")
    x, y = build_xy(df)
    if len(x) < 30:
        raise ValueError(f"Not enough windows for {ticker}")
    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=2,
        random_state=42,
    )
    model.fit(x, y)
    out = OUT_DIR / f"{ticker}.pkl"
    with out.open("wb") as f:
        pickle.dump(model, f)
    print(f"saved {ticker} -> {out}")


if __name__ == "__main__":
    for t in TICKERS:
        try:
            train_one(t)
        except Exception as e:
            print(f"failed {t}: {e}")
