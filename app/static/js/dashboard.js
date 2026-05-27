window.onload = function(){
    tick()
    setInterval(tick, 1000)
    loadWatchlist()
    loadMarketSummary()
    var twoMin = 2 * 60 * 1000
    setInterval(loadWatchlist, twoMin)
    setInterval(loadMarketSummary, twoMin)
}

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

    async function loadMarketSummary() {
      try {
        const res  = await fetch("/dashboard_data");
        const data = await res.json();
        const ids  = { "S&P 500": "sp500", "NASDAQ": "nasdaq", "DOW": "dow" };

        for (const card of data.market_summary) {
          const key = ids[card.name]; if (!key) continue;
          const pe  = document.getElementById(`${key}-price`);
          const ce  = document.getElementById(`${key}-change`);
          if (card.price !== null) {
            pe.textContent = `$${card.price.toLocaleString()}`;
            const { cls, text } = fmtChange(card.change_pct);
            ce.textContent  = text;
            ce.className    = `font-mono text-xs mt-1 ${cls}`;
          } else {
            pe.textContent = "N/A"; ce.textContent = "—";
          }
        }
        document.getElementById("last-updated").textContent = "Updated " + new Date().toLocaleTimeString();
      } catch (e) { console.error("Market error:", e); }
    }

    // ── Watchlist ──
    async function loadWatchlist() {
      const body = document.getElementById("watchlist-body");
      const cnt  = document.getElementById("watchlist-count");
      try {
        const res  = await fetch("/api/watchlist");
        const data = await res.json();

        body.innerHTML = "";
        if (!data.tickers?.length) {
          cnt.textContent = "";
          body.innerHTML  = `<tr><td colspan="4" class="font-mono text-xs text-slate-700 text-center py-10 tracking-widest uppercase">No tickers saved — add one above</td></tr>`;
          return;
        }

        cnt.textContent = `${data.tickers.length} ticker${data.tickers.length !== 1 ? "s" : ""}`;

        for (const ticker of data.tickers) {
          const row = document.createElement("tr");
          row.id    = `row-${ticker}`;
          row.className = "border-t border-slate-800/70 transition-colors";
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
          <a
            href="/stockviewer?ticker=${ticker}"
            class="inline-block font-mono text-xs uppercase tracking-widest px-3 py-1 rounded-sm border border-sky-800 text-sky-400 hover:bg-sky-800/40 transition-colors">
            View →
          </a>
        </td>
            <td class="text-right px-5 py-3">
              <button onclick="removeStock('${ticker}')"
                class="font-mono text-xs text-slate-700 hover:text-red-400 transition-colors uppercase tracking-widest">
                ✕ Remove
              </button>
            </td>`;
          body.appendChild(row);
          fetchQuote(ticker);
        }
      } catch (e) { console.error("Watchlist error:", e); }
    }

    async function fetchQuote(ticker) {
      try {
        const res  = await fetch(`/api/stocks/price?ticker=${ticker}`);
        const data = await res.json();
        if (data.price === null) return;
        const pe = document.getElementById(`price-${ticker}`);
        const ce = document.getElementById(`chg-${ticker}`);
        if (pe) pe.textContent = `$${data.price.toFixed(2)}`;
        if (ce) {
          const { cls, text } = fmtChange(data.change_pct);
          ce.textContent = text;
          ce.className   = `font-mono text-xs text-right px-5 py-3 ${cls}`;
        }
        const open = document.getElementById(`open-${ticker}`);
        const high = document.getElementById(`high-${ticker}`);
        const low = document.getElementById(`low-${ticker}`);
        const volume = document.getElementById(`vol-${ticker}`);
        if (open) open.textContent = `$${data.open}`;
        if (high) high.textContent = `$${data.high}`;
        if (low) low.textContent = `$${data.low}`;
        if (volume) volume.textContent = data.volume;

      } catch (e) { console.error(`Quote error ${ticker}:`, e); }
    }

    async function addStock() {
      const input  = document.getElementById("add-ticker");
      const ticker = input.value.trim().toUpperCase();
      if (!ticker) return;
      try {
        const res  = await fetch("/api/watchlist/add", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticker }),
        });
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        input.value = "";
        loadWatchlist();
      } catch (e) { console.error("Add error:", e); }
    }

    async function removeStock(ticker) {
      try {
        await fetch("/api/watchlist/remove", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticker }),
        });
        loadWatchlist();
      } catch (e) { console.error("Remove error:", e); }
    }

    document.getElementById("add-ticker").addEventListener("keydown", e => {
      if (e.key === "Enter") addStock();
    });