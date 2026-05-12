To test:

run in terminal:
$ app prototype.app

$ curl -X POST http://127.0.0.1:5000/predict \
     -H "Content-Type: application/json" \
     -d '{"ticker":"NVDA"}'

*Might need to have venv
