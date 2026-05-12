from flask import Flask, request, jsonify
import pickle
import yfinance as yf
import numpy as np

# Load trained model using pickel
with open('stock_model.pkl', 'rb') as f:
    model = pickle.load(f)

app = Flask(__name__)

# Feature extraction func (preprocessing data)
def get_features(ticker):
    df = yf.Ticker(ticker).history(period="5Y")
    df = df[['Open', 'Volume']].to_numpy()
    if len(df) < 5:
        raise ValueError("Not enough data to create features")
    # Sliding window: last 4 days
    X = np.zeros((1, 8))
    X[0] = [
        df[-5][0], df[-4][0], df[-3][0], df[-2][0],  # Open prices
        df[-5][1], df[-4][1], df[-3][1], df[-2][1]   # Volumes
    ]
    return X

# Routes
@app.route('/')
def home():
    return "Stock Prediction API is running!"

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json()  # expects {"ticker": "NVDA"}
        ticker = data['ticker'].upper()
        X = get_features(ticker)
        prediction = model.predict(X)[0]
        return jsonify({"ticker": ticker, "prediction": float(prediction)})
    except Exception as e:
        return jsonify({"error": str(e)})

# Run server
if __name__ == '__main__':
    # localhost only, port 5000
    app.run(host='127.0.0.1', port=5000, debug=True)
