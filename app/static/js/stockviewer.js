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
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
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
      <td class="px-5 py-2">
        <canvas id="spark-${ticker}" width="120" height="40"></canvas>
      </td>
      <td class="text-right px-5 py-3 whitespace-nowrap">
        <button onclick="openStockModal('${ticker}')" class="font-mono text-xs text-slate-600 hover:text-sky-400 transition-colors uppercase tracking-widest whitespace-nowrap">View →</button>
      </td>`;
    body.appendChild(row);
  }

  await Promise.all(TOP_STOCKS.map(fetchQuote));
  Promise.all(TOP_STOCKS.map(fetchSparkline));

  document.getElementById("last-updated").textContent =
    new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

let modalPriceChart = null;
let modalGrowthChart = null;
let modalVolumeChart = null;
let modalSharpeChart = null;

function closeStockModal() {
  document.getElementById("stock-modal").classList.add("hidden");
  if (modalPriceChart) { modalPriceChart.destroy(); modalPriceChart = null; }
  if (modalGrowthChart) { modalGrowthChart.destroy(); modalGrowthChart = null; }
  if (modalVolumeChart) { modalVolumeChart.destroy(); modalVolumeChart = null; }
  if (modalSharpeChart) { modalSharpeChart.destroy(); modalSharpeChart = null; }
}

async function openStockModal(ticker) {
  document.getElementById("modal-title").textContent = `Loading metrics for ${ticker}...`;
  document.getElementById("stock-modal").classList.remove("hidden");
  
  try {
    const res = await fetch(`/api/stocks/modal_data?ticker=${ticker}`);
    const swag = await res.json();
    if (swag.error) {
      document.getElementById("modal-title").textContent = `Error: ${swag.error}`;
      return;
    }
    
    document.getElementById("modal-title").textContent = `${ticker} — Blossomberg Metrics`;

    // 1. Price History
    const ctxPrice = document.getElementById("modalPriceChart").getContext("2d");
    const isUp = swag.price_closes[swag.price_closes.length - 1] >= swag.price_closes[0];
    const priceColor = isUp ? "#10b981" : "#ef4444";
    modalPriceChart = new Chart(ctxPrice, {
      type: "line",
      data: {
        labels: swag.price_labels,
        datasets: [{
          label: `${ticker} Price`,
          data: swag.price_closes,
          borderColor: priceColor,
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.1,
          fill: false
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: "#1e293b" }, ticks: { color: "#94a3b8", maxTicksLimit: 10 } },
          y: { grid: { color: "#1e293b" }, ticks: { color: "#94a3b8", callback: v => "$" + v } }
        }
      }
    });

    // 2. Growth Comparison
    const ctxGrowth = document.getElementById("modalGrowthChart").getContext("2d");
    const colors = [
      "#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4"
    ];
    const growthDatasets = swag.growth_datasets.map((dataset, idx) => {
      const isSelected = dataset.ticker === ticker;
      return {
        label: dataset.ticker,
        data: dataset.data,
        borderColor: isSelected ? "#38bdf8" : colors[idx % colors.length],
        borderWidth: isSelected ? 3 : 1.5,
        pointRadius: 0,
        tension: 0.1,
        fill: false
      };
    });
    modalGrowthChart = new Chart(ctxGrowth, {
      type: "line",
      data: {
        labels: swag.monthly_labels,
        datasets: growthDatasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: "#94a3b8" } } },
        scales: {
          x: { grid: { color: "#1e293b" }, ticks: { color: "#94a3b8" } },
          y: { grid: { color: "#1e293b" }, ticks: { color: "#94a3b8", callback: v => v + "%" } }
        }
      }
    });

    // 3. Monthly Volume
    const ctxVolume = document.getElementById("modalVolumeChart").getContext("2d");
    modalVolumeChart = new Chart(ctxVolume, {
      type: "bar",
      data: {
        labels: swag.monthly_labels,
        datasets: [{
          label: "Avg Vol",
          data: swag.monthly_volume,
          backgroundColor: "#4f46e5"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: "#1e293b" }, ticks: { color: "#94a3b8" } },
          y: {
            grid: { color: "#1e293b" },
            ticks: {
              color: "#94a3b8",
              callback: v => Intl.NumberFormat("en-US", { notation: "compact" }).format(v)
            }
          }
        }
      }
    });

    // 4. Sharpe Ratio Comparison
    const ctxSharpe = document.getElementById("modalSharpeChart").getContext("2d");
    const sharpeLabels = swag.sharpe_data.map(d => d.ticker);
    const sharpeRatios = swag.sharpe_data.map(d => d.sharpe_ratio);
    const sharpeColors = swag.sharpe_data.map(d => d.ticker === ticker ? "#34d399" : "#475569");
    modalSharpeChart = new Chart(ctxSharpe, {
      type: "bar",
      data: {
        labels: sharpeLabels,
        datasets: [{
          label: "Sharpe Ratio",
          data: sharpeRatios,
          backgroundColor: sharpeColors
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: "#1e293b" }, ticks: { color: "#94a3b8" } },
          y: { grid: { color: "#1e293b" }, ticks: { color: "#94a3b8" } }
        }
      }
    });
  } catch (err) {
    document.getElementById("modal-title").textContent = `Error loading data: ${err}`;
  }
}

window.onload = function () {
  tick();
  setInterval(tick, 1000);
  loadTopStocks();
  setInterval(loadTopStocks, 2 * 60 * 1000);

  const urlParams = new URLSearchParams(window.location.search);
  const targetTicker = urlParams.get("ticker");
  if (targetTicker) {
    setTimeout(() => {
      openStockModal(targetTicker.toUpperCase());
    }, 300);
  }
};
