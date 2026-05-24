const TOP_STOCKS = [
  "AAPL","MSFT","NVDA","GOOGL","AMZN",
  "META","TSLA","AVGO","JPM","V",
  "WMT","XOM","MA","COST","NFLX"
];

function tick() {
  document.getElementById("clock").textContent =
    new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
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

async function loadTopStocks() {
  const body = document.getElementById("stockviewer-body");
  body.innerHTML = "";

  for (const ticker of TOP_STOCKS) {
    const row = document.createElement("tr");
    row.className = "border-t border-slate-800/70";
    row.innerHTML = `
      <td class="font-mono text-sm font-medium text-sky-400 px-5 py-3">${ticker}</td>
      <td class="font-mono text-sm text-slate-200 text-right px-5 py-3" id="price-${ticker}"><span class="text-slate-700 text-xs">…</span></td>
      <td class="font-mono text-xs text-right px-5 py-3" id="chg-${ticker}">—</td>
      <td class="font-mono text-xs text-slate-400 text-right px-5 py-3" id="open-${ticker}">…</td>
      <td class="font-mono text-xs text-slate-400 text-right px-5 py-3" id="high-${ticker}">…</td>
      <td class="font-mono text-xs text-slate-400 text-right px-5 py-3" id="low-${ticker}">…</td>
      <td class="font-mono text-xs text-slate-400 text-right px-5 py-3" id="vol-${ticker}">…</td>
      <td class="text-right px-5 py-3">
        <a href="#" class="font-mono text-xs text-slate-600 hover:text-sky-400 transition-colors uppercase tracking-widest">View →</a>
      </td>`;
    body.appendChild(row);
  }

  await Promise.all(TOP_STOCKS.map(fetchQuote));

  document.getElementById("last-updated").textContent =
    new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

window.onload = function () {
  tick();
  setInterval(tick, 1000);
  loadTopStocks();
  setInterval(loadTopStocks, 2 * 60 * 1000);
};
