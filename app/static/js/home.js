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

}

function removeStock(ticker){

}

function searchStock() {

}