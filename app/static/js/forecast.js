    const ctx = document.getElementById("chart");
    const tickerInput = document.getElementById("ticker");
    const runButton = document.getElementById("run");
    const metaEl = document.getElementById("meta");
    const errorEl = document.getElementById("error");
    let chart;

    function createChart(payload) {
      if (chart) chart.destroy();
      chart = new Chart(ctx, {
        type: "line",
        data: {
          labels: payload.labels,
          datasets: [
            {
              label: `${payload.ticker} Actual Open`,
              data: payload.actual,
              borderColor: "#0d6efd",
              backgroundColor: "rgba(13, 110, 253, 0.1)",
              borderWidth: 2,
              pointRadius: 1,
              tension: 0.35,
              fill: true
            },
            {
              label: `${payload.ticker} Sliding Window Predicted Open`,
              data: payload.rolling_prediction,
              borderColor: "#fd7e14",
              backgroundColor: "#fd7e14",
              borderWidth: 2,
              pointRadius: 1,
              borderDash: [6, 4],
              spanGaps: true,
              tension: 0.25
            },
            {
              label: `${payload.ticker} Predicted Next Open`,
              data: payload.prediction,
              borderColor: "#198754",
              backgroundColor: "#198754",
              borderWidth: 2,
              pointRadius: 5,
              showLine: true,
              spanGaps: true,
              tension: 0.8
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: {
            duration: 1200,
            easing: "easeOutQuart"
          },
          animations: {
            tension: {
              duration: 1000,
              easing: "linear",
              from: 1,
              to: 0.25,
              loop: true
            }
          },
          interaction: {
            mode: "index",
            intersect: false
          },
          plugins: {
            legend: {
              labels: { color: "#FFFF" }
            },
            tooltip: {
              callbacks: {
                label: (c) => c.parsed.y == null ? "" : `${c.dataset.label}: ${c.parsed.y.toFixed(2)}`
              }
            }
          },
          scales: {
            x: {
              ticks: { color: "#FFFF", maxRotation: 0, autoSkip: true }
            },
            y: {
              ticks: { color: "#FFFF" }
            }
          }
        }
      });
    }

    async function runDemo() {
      const ticker = tickerInput.value.trim().toUpperCase() || "NVDA";
      errorEl.textContent = "";
      metaEl.textContent = "Loading market data and model prediction...";
      const res = await fetch("/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker })
      });
      const payload = await res.json();
      if (!res.ok) {
        metaEl.textContent = "";
        errorEl.textContent = payload.error || "Something went wrong.";
        return;
      }
      createChart(payload);
      const sign = payload.delta >= 0 ? "+" : "";
      metaEl.textContent = `${payload.ticker} last open: ${payload.last_open} | predicted next open: ${payload.predicted_open} | move: ${sign}${payload.delta} (${sign}${payload.delta_pct}%)`;
    }

    runButton.addEventListener("click", runDemo);
    document.querySelectorAll(".quick-ticker").forEach((btn) => {
      btn.addEventListener("click", () => {
        tickerInput.value = btn.dataset.ticker;
        runDemo();
      });
    });
    tickerInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") runDemo();
    });
    runDemo();