const TOP_STOCKS = [
  "AAPL","MSFT","NVDA","GOOGL","AMZN",
  "META","TSLA","AVGO","JPM","V",
  "WMT","XOM","MA","COST","NFLX"
];

// hardcoded company names for the top 15 so we don't have to make extra api calls
const COMPANY_NAMES = {
    "AAPL":  "Apple Inc.",
    "MSFT":  "Microsoft Corp.",
    "NVDA":  "NVIDIA Corp.",
    "GOOGL": "Alphabet Inc.",
    "AMZN":  "Amazon.com Inc.",
    "META":  "Meta Platforms",
    "TSLA":  "Tesla Inc.",
    "AVGO":  "Broadcom Inc.",
    "JPM":   "JPMorgan Chase",
    "V":     "Visa Inc.",
    "WMT":   "Walmart Inc.",
    "XOM":   "ExxonMobil Corp.",
    "MA":    "Mastercard Inc.",
    "COST":  "Costco Wholesale",
    "NFLX":  "Netflix Inc."
};

function tick() {
    // always show EST time
    document.getElementById("clock").textContent =
        new Date().toLocaleTimeString("en-US", {
            timeZone: "America/New_York",
            hour: "2-digit", minute: "2-digit", second: "2-digit"
        }) + " EST";
}

function fmtChange(pct) {
    const up  = pct >= 0;
    const cls = up ? "text-emerald-400" : "text-red-400";
    const sym = up ? "▲" : "▼";
    return { cls, text: `${sym} ${Math.abs(pct).toFixed(2)}%` };
}

async function fetchQuote(ticker) {
    const res  = await fetch(`/api/stocks/price?ticker=${ticker}`);
    const data = await res.json();

    const set = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };

    if (data.price === null) {
        set(`price-${ticker}`, "N/A");
        set(`chg-${ticker}`,   "—");
        set(`open-${ticker}`,  "N/A");
        set(`high-${ticker}`,  "N/A");
        set(`low-${ticker}`,   "N/A");
        set(`vol-${ticker}`,   "N/A");
        return;
    }

    set(`price-${ticker}`, `$${data.price.toFixed(2)}`);
    set(`open-${ticker}`,  data.open   != null ? `$${data.open.toFixed(2)}`  : "N/A");
    set(`high-${ticker}`,  data.high   != null ? `$${data.high.toFixed(2)}`  : "N/A");
    set(`low-${ticker}`,   data.low    != null ? `$${data.low.toFixed(2)}`   : "N/A");
    set(`vol-${ticker}`,   data.volume != null ? data.volume.toLocaleString() : "N/A");

    if (data.change_pct != null) {
        const chgEl = document.getElementById(`chg-${ticker}`);
        const { cls, text } = fmtChange(data.change_pct);
        if (chgEl) { chgEl.textContent = text; chgEl.className = `font-mono text-xs text-right px-5 py-3 ${cls}`; }
    } else {
        set(`chg-${ticker}`, "—");
    }
}

async function fetchSparkline(ticker) {
    try {
        const res = await fetch(`/api/stocks/history?ticker=${ticker}&period=1mo`);
        const data = await res.json();
        if (data.error || !data.prices || data.prices.length < 2) return;

        const canvas = document.getElementById(`spark-${ticker}`);
        if (!canvas) return;

        const prices = data.prices;
        const isUp = prices[prices.length - 1] >= prices[0];
        const color = isUp ? "#34d399" : "#f87171";

        new Chart(canvas, {
            type: "line",
            data: {
                labels: data.labels,
                datasets: [{
                    data: prices,
                    borderColor: color,
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.4,
                    fill: true,
                    backgroundColor: isUp ? "rgba(52,211,153,0.08)" : "rgba(248,113,113,0.08)",
                }]
            },
            options: {
                responsive: false,
                animation: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { display: false },
                    // enable tooltip so hovering shows the exact price
                    tooltip: {
                        enabled: true,
                        backgroundColor: "#0f172a",
                        borderColor: "#334155",
                        borderWidth: 1,
                        titleColor: "#94a3b8",
                        bodyColor: "#e2e8f0",
                        titleFont: { family: '"IBM Plex Mono"', size: 9 },
                        bodyFont:  { family: '"IBM Plex Mono"', size: 9 },
                        padding: 5,
                        callbacks: {
                            title: ctx => ctx[0].label,
                            label: ctx => "$" + ctx.parsed.y.toFixed(2)
                        }
                    }
                },
                scales: {
                    x: { display: false },
                    y: { display: false }
                }
            }
        });
    } catch (_) {}
}

async function loadTopStocks() {
    const body = document.getElementById("stockviewer-body");
    body.innerHTML = "";

    for (const ticker of TOP_STOCKS) {
        const companyName = COMPANY_NAMES[ticker] || "";
        const row = document.createElement("tr");
        row.className = "border-t border-slate-800/70";
        row.innerHTML = `
            <td class="font-mono text-sm font-medium text-sky-400 px-5 py-3">${ticker}</td>
            <td class="font-mono text-xs text-slate-400 px-5 py-3">${companyName}</td>
            <td class="font-mono text-sm text-slate-200 text-right px-5 py-3" id="price-${ticker}"><span class="text-slate-700 text-xs">…</span></td>
            <td class="font-mono text-xs text-right px-5 py-3" id="chg-${ticker}">—</td>
            <td class="font-mono text-xs text-slate-400 text-right px-5 py-3" id="open-${ticker}">…</td>
            <td class="font-mono text-xs text-slate-400 text-right px-5 py-3" id="high-${ticker}">…</td>
            <td class="font-mono text-xs text-slate-400 text-right px-5 py-3" id="low-${ticker}">…</td>
            <td class="font-mono text-xs text-slate-400 text-right px-5 py-3" id="vol-${ticker}">…</td>
            <td class="px-5 py-2 cursor-pointer" title="Click to view ${ticker}" onclick="window.location.href='/stock/${ticker}'">
                <canvas id="spark-${ticker}" width="120" height="40" style="cursor:pointer"></canvas>
            </td>
            <td class="text-right px-5 py-3 whitespace-nowrap">
                <a href="/stock/${ticker}" class="font-mono text-xs text-slate-600 hover:text-sky-400 transition-colors uppercase tracking-widest whitespace-nowrap">View →</a>
            </td>`;
        body.appendChild(row);
    }

    await Promise.all(TOP_STOCKS.map(fetchQuote));
    Promise.all(TOP_STOCKS.map(fetchSparkline));

    document.getElementById("last-updated").textContent =
        new Date().toLocaleTimeString("en-US", {
            timeZone: "America/New_York",
            hour: "2-digit", minute: "2-digit", second: "2-digit"
        }) + " EST";
}

window.onload = function () {
    tick();
    setInterval(tick, 1000);
    loadTopStocks();
    setInterval(loadTopStocks, 2 * 60 * 1000);
};
