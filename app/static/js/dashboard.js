window.onload = function(){
    tick()
    setInterval(tick, 1000)
    loadWatchlist()
    loadMarketSummary()
    loadMarketStatus()
    var twoMin = 2 * 60 * 1000
    setInterval(loadWatchlist, twoMin)
    setInterval(loadMarketSummary, twoMin)
    setInterval(loadMarketStatus, 60 * 1000)  // recheck market open/close every minute
}

function tick() {
    // always show EST no matter where the user is located
    var estTime = new Date().toLocaleTimeString("en-US", {
        timeZone: "America/New_York",
        hour: "2-digit", minute: "2-digit", second: "2-digit"
    })
    document.getElementById("clock").textContent = estTime
}

function fmtChange(pct) {
    var up  = pct >= 0
    var cls = up ? "text-emerald-400" : "text-red-400"
    var sym = up ? "▲" : "▼"
    return { cls: cls, text: sym + " " + Math.abs(pct).toFixed(2) + "%" }
}

async function loadMarketStatus() {
    try {
        var res  = await fetch("/api/market/status")
        var data = await res.json()
        var dot  = document.getElementById("market-dot")
        var txt  = document.getElementById("market-text")
        if (data.is_open) {
            dot.className = "w-2 h-2 rounded-full bg-emerald-400 inline-block animate-pulse"
            txt.textContent = "Market Open"
            txt.className = "font-mono text-xs text-emerald-400 uppercase tracking-widest"
        } else {
            dot.className = "w-2 h-2 rounded-full bg-slate-600 inline-block"
            txt.textContent = "Market Closed"
            txt.className = "font-mono text-xs text-slate-600 uppercase tracking-widest"
        }
    } catch (e) { console.error("market status error:", e) }
}

async function loadMarketSummary() {
    try {
        var res  = await fetch("/dashboard_data")
        var data = await res.json()
        var ids  = { "S&P 500": "sp500", "NASDAQ": "nasdaq", "DOW": "dow" }

        for (var card of data.market_summary) {
            var key = ids[card.name]
            if (!key) continue
            var pe = document.getElementById(key + "-price")
            var ce = document.getElementById(key + "-change")
            if (card.price !== null) {
                pe.textContent = "$" + card.price.toLocaleString()
                var fmted = fmtChange(card.change_pct)
                ce.textContent = fmted.text
                ce.className   = "font-mono text-xs mt-1 " + fmted.cls
            } else {
                pe.textContent = "N/A"
                ce.textContent = "—"
            }
        }
        var estNow = new Date().toLocaleTimeString("en-US", {
            timeZone: "America/New_York",
            hour: "2-digit", minute: "2-digit"
        })
        document.getElementById("last-updated").textContent = "Updated " + estNow + " EST"
    } catch (e) { console.error("Market error:", e) }
}

// ── Watchlist ──
async function loadWatchlist() {
    var body = document.getElementById("watchlist-body")
    var cnt  = document.getElementById("watchlist-count")
    try {
        var res  = await fetch("/api/watchlist")
        var data = await res.json()

        body.innerHTML = ""
        if (!data.tickers?.length) {
            cnt.textContent = ""
            body.innerHTML  = `<tr><td colspan="9" class="font-mono text-xs text-slate-700 text-center py-10 tracking-widest uppercase">No tickers saved — add one above</td></tr>`
            return
        }

        cnt.textContent = data.tickers.length + " ticker" + (data.tickers.length !== 1 ? "s" : "")

        for (var ticker of data.tickers) {
            var row = document.createElement("tr")
            row.id    = "row-" + ticker
            row.className = "border-t border-slate-800/70 transition-colors"
            row.innerHTML = `
                <td class="font-mono text-sm font-medium text-sky-400 px-5 py-3">${ticker}</td>
                <td class="font-mono text-sm text-slate-200 text-right px-5 py-3" id="price-${ticker}">
                    <span class="text-slate-700 text-xs">…</span>
                </td>
                <td class="font-mono text-xs text-slate-600 text-right px-5 py-3" id="chg-${ticker}">—</td>
                <td class="font-mono text-xs text-slate-400 text-right px-5 py-3" id="open-${ticker}">—</td>
                <td class="font-mono text-xs text-slate-400 text-right px-5 py-3" id="high-${ticker}">—</td>
                <td class="font-mono text-xs text-slate-400 text-right px-5 py-3" id="low-${ticker}">—</td>
                <td class="font-mono text-xs text-slate-400 text-right px-5 py-3" id="vol-${ticker}">—</td>
                <td class="text-right px-5 py-3">
                    <a href="/stock/${ticker}"
                        class="inline-block font-mono text-xs uppercase tracking-widest px-3 py-1 rounded-sm border border-sky-800 text-sky-400 hover:bg-sky-800/40 transition-colors">
                        View →
                    </a>
                </td>
                <td class="text-right px-5 py-3">
                    <button onclick="removeStock('${ticker}')"
                        class="font-mono text-xs text-slate-700 hover:text-red-400 transition-colors uppercase tracking-widest">
                        ✕ Remove
                    </button>
                </td>`
            body.appendChild(row)
            fetchQuote(ticker)
        }
    } catch (e) { console.error("Watchlist error:", e) }
}

async function fetchQuote(ticker) {
    try {
        var res  = await fetch("/api/stocks/price?ticker=" + ticker)
        var data = await res.json()
        if (data.price === null) return
        var pe = document.getElementById("price-" + ticker)
        var ce = document.getElementById("chg-" + ticker)
        if (pe) pe.textContent = "$" + data.price.toFixed(2)
        if (ce) {
            var fmted = fmtChange(data.change_pct)
            ce.textContent = fmted.text
            ce.className   = "font-mono text-xs text-right px-5 py-3 " + fmted.cls
        }
        var open   = document.getElementById("open-"  + ticker)
        var high   = document.getElementById("high-"  + ticker)
        var low    = document.getElementById("low-"   + ticker)
        var volume = document.getElementById("vol-"   + ticker)
        if (open)   open.textContent   = data.open   != null ? "$" + data.open.toFixed(2)       : "N/A"
        if (high)   high.textContent   = data.high   != null ? "$" + data.high.toFixed(2)       : "N/A"
        if (low)    low.textContent    = data.low    != null ? "$" + data.low.toFixed(2)        : "N/A"
        if (volume) volume.textContent = data.volume != null ? data.volume.toLocaleString()     : "N/A"
    } catch (e) { console.error("Quote error " + ticker + ":", e) }
}

async function addStock() {
    var input  = document.getElementById("add-ticker")
    var ticker = input.value.trim().toUpperCase()
    if (!ticker) return
    try {
        var res  = await fetch("/api/watchlist/add", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker: ticker }),
        })
        var data = await res.json()
        if (data.error) { alert(data.error); return }
        input.value = ""
        loadWatchlist()
    } catch (e) { console.error("Add error:", e) }
}

async function removeStock(ticker) {
    try {
        await fetch("/api/watchlist/remove", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker: ticker }),
        })
        loadWatchlist()
    } catch (e) { console.error("Remove error:", e) }
}

document.getElementById("add-ticker").addEventListener("keydown", function(e) {
    if (e.key === "Enter") addStock()
})
