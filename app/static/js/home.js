window.onload = function(){
    loadWatchlist()
    var fivemin = 5 * 60 * 1000
    setInterval(loadWatchlist, fivemin)
}

function loadWatchlist(){
    fetch("/api/watchlist")
    .then(function(response) {
        return response.json()
    })
    .then(function(data){
        var tickerList = data.tickers
        var tableBody = document.getElementById("watchlist-body")
        tableBody.innerHTML = ""

        for(var i = 0; i < tickerList.length; i++){
            var ticker = tickerList[i]

            fetch("/api/stocks/price?ticker=" + ticker)
            .then(function(response){
                return response.json()
            })
            .then(function(stockData) {
                var newRow = document.createElement("tr")
                newRow.innerHTML = "<td>" + stockData.ticker + "</td>" + "<td>$" + stockData.price + "</td>" + "<td><button onclick='removeStock(\"" + stockData.ticker + "\")'>Remove</button></td>"
                tableBody.appendChild(newRow)
        })
    }
    })
}

function addStock() {
    var inputBox = document.getElementById("add-ticker")
    var ticker = inputBox.value
    ticker = ticker.toUpperCase()

    fetch("/api/watchlist/add", {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ticker: ticker})})
    .then(function(response){
        return response.json()
    })
    .then(function(result){
        inputBox.value = ""
        loadWatchlist()
    })
}

function removeStock(ticker){
    fetch("/api/watchlist/remove", {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ticker: ticker})})
    .then(function(response){
        return response.json()
    })
    .then(function(result){
        loadWatchlist()
    })
}

function searchStock() {
    var searchBox = document.getElementById("navbar-search")
    var query = searchBox.value
    query = query.toUpperCase()

    fetch("/api/stocks/search?q=" + query)
    .then(function(response){
        return response.json()
    })
    .then(function(result){
        var resultSpan = document.getElementById("search-result")
        resultSpan.innerText = result.name + "- $" + result.price
    })
}