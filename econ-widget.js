/* Big Brain Ape — econ calendar widget
   Past prints vs consensus + next-print guidance.
   Works for PCE and any other indicator in data/econ-calendar.json
*/
(function () {
  const SRC = (document.currentScript && document.currentScript.getAttribute("data-src")) || "data/econ-calendar.json";
  const MOUNT = document.getElementById("econ-widget") || (function () {
    const d = document.createElement("div");
    d.id = "econ-widget";
    return d;
  })();

  const css = `
  #econ-widget{max-width:800px;margin:0 auto 8px;padding:0 20px 20px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#e5e7eb}
  #econ-widget .ew-card{background:#13131f;border:1px solid #1f1f35;border-radius:16px;padding:20px}
  #econ-widget h3{margin:0 0 4px;font-size:18px}
  #econ-widget .ew-sub{color:#6b7280;font-size:13px;margin-bottom:14px}
  #econ-widget .ew-tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
  #econ-widget .ew-tab{background:#0a0a0f;border:1px solid #1f1f35;color:#9ca3af;border-radius:999px;padding:6px 12px;font-size:12px;font-weight:700;cursor:pointer}
  #econ-widget .ew-tab.on{border-color:#00d9ff;color:#00d9ff}
  #econ-widget canvas{width:100%;height:180px;display:block;background:#0a0a0f;border-radius:10px}
  #econ-widget .ew-guide{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:12px}
  #econ-widget .ew-box{border-radius:10px;padding:10px;font-size:12px;line-height:1.4}
  #econ-widget .soft{background:#0d1a0d;border:1px solid #00ff9d;color:#00ff9d}
  #econ-widget .mid{background:#111122;border:1px solid #00d9ff;color:#e5e7eb}
  #econ-widget .hot{background:#1a0d0d;border:1px solid #ff4444;color:#ff6b6b}
  #econ-widget .ew-meta{margin-top:10px;font-size:12px;color:#9ca3af}
  #econ-widget .ew-meta b{color:#fff}
  @media(max-width:640px){#econ-widget .ew-guide{grid-template-columns:1fr}}
  `;
  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  function draw(canvas, series) {
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    canvas.width = w * dpr; canvas.height = h * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);
    if (!series.length) {
      ctx.fillStyle = "#6b7280";
      ctx.font = "13px sans-serif";
      ctx.fillText("No history loaded for this series yet.", 16, h / 2);
      return;
    }
    const vals = series.flatMap(s => [s.actual, s.forecast].filter(v => typeof v === "number"));
    const min = Math.min(...vals) - 0.15, max = Math.max(...vals) + 0.15;
    const padL = 36, padR = 12, padT = 16, padB = 28;
    const x = i => padL + (i * (w - padL - padR)) / Math.max(series.length - 1, 1);
    const y = v => padT + (1 - (v - min) / (max - min)) * (h - padT - padB);
    ctx.strokeStyle = "#1f1f35"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(padL, padT); ctx.lineTo(padL, h - padB); ctx.lineTo(w - padR, h - padB); ctx.stroke();
    ctx.strokeStyle = "rgba(255,215,0,0.45)"; ctx.lineWidth = 2; ctx.setLineDash([4, 4]);
    ctx.beginPath();
    series.forEach((s, i) => { const yy = y(s.forecast); i ? ctx.lineTo(x(i), yy) : ctx.moveTo(x(i), yy); });
    ctx.stroke(); ctx.setLineDash([]);
    ctx.strokeStyle = "#00d9ff"; ctx.lineWidth = 2.5;
    ctx.beginPath();
    series.forEach((s, i) => { const yy = y(s.actual); i ? ctx.lineTo(x(i), yy) : ctx.moveTo(x(i), yy); });
    ctx.stroke();
    series.forEach((s, i) => {
      ctx.fillStyle = s.actual > s.forecast ? "#ff6b6b" : (s.actual < s.forecast ? "#00ff9d" : "#00d9ff");
      ctx.beginPath(); ctx.arc(x(i), y(s.actual), 3.5, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "#6b7280"; ctx.font = "10px sans-serif"; ctx.textAlign = "center";
      ctx.fillText(s.period || "", x(i), h - 10);
    });
    ctx.fillStyle = "#9ca3af"; ctx.font = "10px sans-serif"; ctx.textAlign = "left";
    ctx.fillText(max.toFixed(1), 4, padT + 4);
    ctx.fillText(min.toFixed(1), 4, h - padB);
  }

  function render(data, id) {
    const list = data.indicators || [];
    const cur = list.find(i => i.id === id) || list[0];
    if (!cur) return;
    const n = cur.next || {};
    MOUNT.innerHTML = `
      <div class="ew-card">
        <h3>Econ tape — ${cur.name}</h3>
        <div class="ew-sub">Past prints vs consensus (yellow dashes) + next-print guidance. Same widget for every release.</div>
        <div class="ew-tabs">${list.map(i => `<button class="ew-tab ${i.id===cur.id?"on":""}" data-id="${i.id}">${i.id}</button>`).join("")}</div>
        <canvas id="ew-chart"></canvas>
        <div class="ew-guide">
          <div class="ew-box soft"><b>SOFT / RISK-ON</b><br>${n.soft || "Print below consensus"}</div>
          <div class="ew-box mid"><b>IN-LINE</b><br>${n.inline || (n.forecast != null ? ("Consensus " + n.forecast) : "Awaiting consensus")}</div>
          <div class="ew-box hot"><b>HOT / RISK-OFF</b><br>${n.hot || "Print above consensus"}</div>
        </div>
        <div class="ew-meta">
          Next: <b>${n.release || "—"} ${n.time || ""}</b>
          ${n.period ? " · " + n.period : ""}
          ${n.forecast != null ? " · Cons " + n.forecast + (cur.unit || "") : ""}
          ${n.forecastMom != null ? " · core m/m " + n.forecastMom + "%" : ""}
          ${n.actual != null ? " · actual <b>" + n.actual + "</b>" : ""}
          <div style="margin-top:6px">${n.note || ""}</div>
        </div>
      </div>`;
    const canvas = MOUNT.querySelector("#ew-chart");
    draw(canvas, cur.history || []);
    MOUNT.querySelectorAll(".ew-tab").forEach(btn => {
      btn.onclick = () => render(data, btn.getAttribute("data-id"));
    });
  }

  fetch(SRC).then(r => r.json()).then(d => render(d, d.nextFocus || "PCE")).catch(() => {
    MOUNT.innerHTML = "<div class='ew-card'>Could not load econ calendar.</div>";
  });
})();
