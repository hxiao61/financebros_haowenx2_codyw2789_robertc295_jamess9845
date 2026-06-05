# Blossomberg Terminal by financebros

## Roster/Roles:
- Haowen Xiao: Frontend, UI, Overall Infrastructure, Project Manager, deployment
- Cody Wong: SQLite, API integration, Stock datasets, backend
- Robert Chen: Flask, routing, sessions, Authentication, portfolio pages
- James Sun: Machine learning, AI integration, models, Forecast, Prediction, Review

## Description:
Blossomberg Terminal is a simpled-down and modernized clone of the Bloomberg Terminal that uses live stock data, charts, and ML forecasting with an AI analysis layer for market exploration and learning. The real Bloomberg Terminal costs almost $25,000 / year and has a UI that was built in the 1980s that is very intimidating for beginners. Retail traders and students who want to learn can use this to learn more about stocks and other features of the stock market before deciding if they need a full Bloomberg terminal.

## Live Site:
Our program is hosted live [financebros.app](http://financebros.app) OR [138.197.98.11](https://138.197.98.117)

### FEATURE SPOTLIGHT
* Search any stock ticker and view live and historical price charts
* Compare two equities side by side with growth and volume visualizations
* ML forecast page with Scikit-learn regression models and confidence intervals
* AI Analysis panel powered by OpenRouter — ask questions like "Why did NVDA rise today?"
* Portfolio / watchlist system tied to your account

### KNOWN BUGS/ISSUES
* None yet

## Install Guide:

Click the green button on the repo, and choose the SSH clone option. Copy the link and open a terminal session.
```
$ git clone git@github.com:hxiao61/financebros_haowenx2_codyw2789_robertc295_jamess9845.git
$ cd financebros_haowenx2_codyw2789_robertc295_jamess9845
$ python -m venv venv
```
For Linux and Mac users

```
$ source venv/bin/activate
$ pip install -r requirements.txt
```

For Windows users

```
$ venv\Scripts\activate
$ pip install -r requirements.txt
```

Now open on [localhost](http://127.0.0.1:5002)

## Launch Codes:
In terminal, access project root directory and run the command:

```
~$ cd app
~$ python3 build_db.py
~$ python3 app.py
```
