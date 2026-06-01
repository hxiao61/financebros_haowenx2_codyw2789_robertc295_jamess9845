const $ = id => document.getElementById(id);

function fmt(n) {
  if (n == null) return '—';
  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtShares(n) {
  if (n == null) return '—';
  return parseFloat(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 4 });
}

function glClass(n) {
  if (n == null) return 'text-slate-400';
  return n >= 0 ? 'text-emerald-400' : 'text-red-400';
}

async function loadState() {
  const res = await fetch('/api/paper/state');
  const d = await res.json();

  $('stat-cash').textContent   = fmt(d.cash);
  $('stat-mkt').textContent    = fmt(d.total_mkt);
  $('stat-equity').textContent = fmt(d.total_equity);

  const glEl  = $('stat-gl');
  const glPct = $('stat-gl-pct');
  glEl.textContent  = (d.total_gl >= 0 ? '+' : '') + fmt(d.total_gl);
  glEl.className    = 'font-mono text-xl font-semibold ' + glClass(d.total_gl);
  glPct.textContent = (d.total_gl_pct >= 0 ? '+' : '') + d.total_gl_pct + '%';

  // Holdings
  const hBody = $('holdings-body');
  if (d.holdings.length === 0) {
    hBody.innerHTML = `<tr><td colspan="8" class="font-mono text-xs text-slate-700 text-center py-10 tracking-widest uppercase">No holdings yet — place a buy order above</td></tr>`;
  } else {
    hBody.innerHTML = d.holdings.map(h => `
      <tr>
        <td class="font-mono text-sm text-slate-200 px-5 py-3 font-semibold">
          <a href="/stock/${h.ticker}" class="hover:text-sky-400 transition-colors">${h.ticker}</a>
        </td>
        <td class="font-mono text-sm text-slate-300 text-right px-5 py-3">${fmtShares(h.shares)}</td>
        <td class="font-mono text-sm text-slate-400 text-right px-5 py-3">${fmt(h.avg_cost)}</td>
        <td class="font-mono text-sm text-slate-300 text-right px-5 py-3">${h.cur_price != null ? fmt(h.cur_price) : '—'}</td>
        <td class="font-mono text-sm text-slate-300 text-right px-5 py-3">${fmt(h.mkt_value)}</td>
        <td class="font-mono text-sm text-right px-5 py-3 ${glClass(h.gain_loss)}">${h.gain_loss != null ? (h.gain_loss >= 0 ? '+' : '') + fmt(h.gain_loss) : '—'}</td>
        <td class="font-mono text-sm text-right px-5 py-3 ${glClass(h.gain_pct)}">${h.gain_pct != null ? (h.gain_pct >= 0 ? '+' : '') + h.gain_pct + '%' : '—'}</td>
        <td class="text-right px-5 py-3">
          <button onclick="sellAll('${h.ticker}', ${h.shares})"
                  class="font-mono text-xs uppercase tracking-widest text-slate-600 hover:text-red-400 transition-colors">
            Sell All
          </button>
        </td>
      </tr>
    `).join('');
  }

  // Transactions
  const tBody = $('txn-body');
  if (d.transactions.length === 0) {
    tBody.innerHTML = `<tr><td colspan="6" class="font-mono text-xs text-slate-700 text-center py-10 tracking-widest uppercase">No transactions yet</td></tr>`;
  } else {
    tBody.innerHTML = d.transactions.map(t => `
      <tr>
        <td class="font-mono text-xs text-slate-500 px-5 py-2.5">${t.created_at}</td>
        <td class="font-mono text-xs uppercase tracking-widest px-5 py-2.5 ${t.action === 'BUY' ? 'text-emerald-400' : 'text-red-400'}">${t.action}</td>
        <td class="font-mono text-sm text-slate-200 px-5 py-2.5 font-semibold">${t.ticker}</td>
        <td class="font-mono text-sm text-slate-300 text-right px-5 py-2.5">${fmtShares(t.shares)}</td>
        <td class="font-mono text-sm text-slate-400 text-right px-5 py-2.5">${fmt(t.price)}</td>
        <td class="font-mono text-sm text-slate-300 text-right px-5 py-2.5">${fmt(t.total)}</td>
      </tr>
    `).join('');
  }
}

async function executeTrade(action) {
  const ticker = $('trade-ticker').value.trim().toUpperCase();
  const shares = $('trade-shares').value;
  const msgEl  = $('trade-msg');

  if (!ticker || !shares) {
    msgEl.textContent = 'Enter a ticker and share count.';
    msgEl.className   = 'font-mono text-xs text-amber-400 ml-2';
    return;
  }

  msgEl.textContent = 'Processing…';
  msgEl.className   = 'font-mono text-xs text-slate-500 ml-2';

  const endpoint = action === 'BUY' ? '/api/paper/buy' : '/api/paper/sell';
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, shares: parseFloat(shares) }),
  });
  const d = await res.json();

  if (d.error) {
    msgEl.textContent = d.error;
    msgEl.className   = 'font-mono text-xs text-red-400 ml-2';
  } else {
    const sign = action === 'BUY' ? 'Bought' : 'Sold';
    msgEl.textContent = `${sign} ${fmtShares(d.shares)} ${d.ticker} @ ${fmt(d.price)}`;
    msgEl.className   = 'font-mono text-xs text-emerald-400 ml-2';
    $('trade-ticker').value = '';
    $('trade-shares').value = '';
    loadState();
  }
}

async function sellAll(ticker, shares) {
  const msgEl = $('trade-msg');
  msgEl.textContent = `Selling all ${ticker}…`;
  msgEl.className   = 'font-mono text-xs text-slate-500 ml-2';

  const res = await fetch('/api/paper/sell', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, shares }),
  });
  const d = await res.json();

  if (d.error) {
    msgEl.textContent = d.error;
    msgEl.className   = 'font-mono text-xs text-red-400 ml-2';
  } else {
    msgEl.textContent = `Sold all ${ticker}`;
    msgEl.className   = 'font-mono text-xs text-emerald-400 ml-2';
    loadState();
  }
}

async function confirmReset() {
  if (!confirm('Reset your paper portfolio to $100,000 cash? This cannot be undone.')) return;
  await fetch('/api/paper/reset', { method: 'POST' });
  $('trade-msg').textContent = 'Portfolio reset.';
  $('trade-msg').className   = 'font-mono text-xs text-sky-400 ml-2';
  loadState();
}

loadState();