    function setQ(text) {
      document.getElementById("question").value = text;
      askAI();
    }

    async function askAI() {
      const q = document.getElementById("question").value.trim();
      if (!q) return;

      document.getElementById("answer-box").classList.add("hidden");
      document.getElementById("error-box").classList.add("hidden");
      document.getElementById("loading").classList.remove("hidden");

      const res  = await fetch("/api/ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q })
      });
      const data = await res.json();

      document.getElementById("loading").classList.add("hidden");

      if (!res.ok || data.error) {
        document.getElementById("error-box").textContent = data.error || "Something went wrong.";
        document.getElementById("error-box").classList.remove("hidden");
        return;
      }

      document.getElementById("answer-box").textContent = data.answer;
      document.getElementById("answer-box").classList.remove("hidden");
    }

    document.getElementById("question").addEventListener("keydown", e => {
      if (e.key === "Enter") askAI();
    });