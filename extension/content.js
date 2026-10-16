/* Panel de margen y botón "Vigilar este producto" en las páginas de producto de amazon.com. */
(function () {
  const L = window.RadarLib;
  const asin = L.extractAsin(location.href, document);
  if (!asin || document.getElementById("radar-compras-host")) return;

  const send = (m) => chrome.runtime.sendMessage(m);
  const titleEl = document.getElementById("productTitle");
  const title = titleEl ? titleEl.textContent.trim().slice(0, 300) : "";
  function pagePrice() {
    const sel = ["#corePrice_feature_div .a-price .a-offscreen", "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
      "#apex_desktop .a-price .a-offscreen", ".a-price .a-offscreen"];
    for (const s of sel) { const el = document.querySelector(s); const p = el && L.parsePrice(el.textContent); if (p) return p; }
    return null;
  }

  const host = document.createElement("div");
  host.id = "radar-compras-host";
  host.style.cssText = "all:initial;position:fixed;right:16px;bottom:16px;z-index:2147483646";
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `
  <style>
  :host{all:initial}
  *{box-sizing:border-box}
  .card{width:300px;font:14px/1.45 system-ui,"Segoe UI",sans-serif;color:#0F2A33;background:#fff;border:1px solid #D3DCDB;border-radius:12px;box-shadow:0 8px 28px rgba(15,42,51,.22);overflow:hidden}
  header{display:flex;align-items:center;justify-content:space-between;gap:8px;background:#0F2A33;color:#EAF3F2;padding:10px 12px;font-weight:600}
  header button{all:unset;cursor:pointer;color:#9DB8BD;font-size:18px;line-height:1;padding:0 4px}
  .body{padding:12px;display:flex;flex-direction:column;gap:10px}
  .tag{display:inline-block;background:#F0B323;color:#3A2A00;font-weight:600;font-size:12px;padding:1px 10px 1px 8px;border-radius:3px 999px 999px 3px;margin-bottom:2px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
  label{display:flex;flex-direction:column;gap:3px;font-size:12px;color:#566D74}
  input{font:inherit;font-size:14px;color:#0F2A33;padding:6px 8px;border:1px solid #D3DCDB;border-radius:6px;width:100%}
  .res{border-radius:8px;padding:10px 12px}
  .res.ok{background:#DCF1E5;color:#1B7F4B}.res.mid{background:#FBEBC8;color:#8A5A00}.res.no{background:#F8DEDB;color:#B3342B}
  .res strong{font-size:20px}.res span{display:block;font-size:12px}
  .min{font-size:12px;color:#566D74;margin:0}.min b{color:#0F2A33}
  button.main{font:inherit;font-weight:600;border:0;border-radius:8px;padding:9px 12px;background:#0B6E75;color:#fff;cursor:pointer;width:100%}
  button.main:disabled{opacity:.6;cursor:default}
  .msg{font-size:13px;margin:0;min-height:1.2em}.msg.err{color:#B3342B}.msg.good{color:#1B7F4B}
  a{color:#0B6E75;font-weight:600}
  .hide{display:none}
  </style>
  <div class="card">
    <header><span>Radar de Compras</span><button id="min" aria-label="Minimizar">&minus;</button></header>
    <div class="body" id="body"></div>
  </div>`;
  document.documentElement.appendChild(host);
  const $ = (id) => root.getElementById(id);

  let S = null, watched = null;
  function fmt(n) { return (n < 0 ? "-" : "") + "$" + Math.abs(n).toFixed(2); }
  const pct = (n) => Math.round(n) + "%";

  function login() {
    $("body").innerHTML = '<p style="margin:0">Inicia sesión desde el icono de la extensión (arriba a la derecha en Chrome) para ver el margen de este producto.</p>';
  }
  function view() {
    const price = pagePrice();
    $("body").innerHTML = `
      <div><span class="tag">ASIN ${asin}</span></div>
      <div class="grid">
        <label>Precio en Amazon<input id="pr" type="number" step="0.01" min="0" value="${price || ""}"></label>
        <label>Tu precio de venta<input id="vt" type="number" step="0.01" min="0" value="${watched && watched.venta_est ? watched.venta_est : ""}"></label>
        <label>Envío al comprador<input id="sh" type="number" step="0.01" min="0" value="${watched && watched.envio_est ? watched.envio_est : ""}"></label>
      </div>
      ${price ? "" : '<p class="min">No encontré el precio en esta página; escríbelo a mano.</p>'}
      <div id="out"></div>
      <button class="main" id="go">${watched ? "Actualizar este producto" : "Vigilar este producto"}</button>
      <p class="msg" id="msg" role="status"></p>`;
    ["pr", "vt", "sh"].forEach((i) => $(i).addEventListener("input", calc));
    $("go").addEventListener("click", save);
    calc();
  }
  const val = (id) => { const n = parseFloat($(id).value); return isFinite(n) ? n : 0; };
  function calc() {
    const price = val("pr"), venta = val("vt"), ship = val("sh");
    if (!(price > 0 && venta > 0)) { $("out").innerHTML = '<p class="min">Escribe tu precio de venta para ver la ganancia.</p>'; return; }
    const e = L.evaluate(S, price, ship, venta);
    const word = { ok: "Comprar", mid: "Negociar", no: "Descartar" }[e.verdict];
    $("out").innerHTML = `<div class="res ${e.verdict}"><strong>${word}</strong><span>Ganas ${fmt(e.net)} por unidad (${pct(e.mg)} de margen, ROI ${pct(e.roi)})</span><span>Costo con impuesto y empaque: ${fmt(e.total)}</span></div>
      <p class="min">${e.minVenta ? "Para tu margen de " + pct(S.meta) + " vende a <b>" + fmt(e.minVenta) + "</b> o más." : "Con esa comisión no se alcanza tu margen."}</p>`;
  }
  async function save() {
    const msg = $("msg"); $("go").disabled = true; msg.className = "msg"; msg.textContent = "";
    const venta = val("vt"), ship = val("sh");
    const r = await send({ type: "api", path: "/productos", method: "POST",
      body: { asin, titulo: title || null, venta_est: venta > 0 ? venta : null, envio_est: ship > 0 ? ship : null } });
    $("go").disabled = false;
    if (!r.ok) { msg.className = "msg err"; msg.textContent = r.error; return; }
    watched = Object.assign(watched || {}, { venta_est: venta, envio_est: ship });
    $("go").textContent = "Actualizar este producto";
    msg.className = "msg good"; msg.textContent = "Guardado. Ya lo vigila tu radar.";
  }
  async function init() {
    const st = await send({ type: "status" });
    if (!st.data.loggedIn) return login();
    const [a, p] = await Promise.all([send({ type: "api", path: "/ajustes" }), send({ type: "api", path: "/productos" })]);
    if (!a.ok) { $("body").textContent = a.error || "No se pudo cargar."; return; }
    S = { tax: +a.data.impuesto_pct, pack: +a.data.empaque, com: +a.data.comision_pct, fijo: +a.data.cargo_fijo, meta: +a.data.margen_minimo };
    watched = (p.ok && p.data.find((x) => x.asin === asin)) || null;
    view();
  }
  let hidden = false;
  $("min").addEventListener("click", () => { hidden = !hidden; $("body").classList.toggle("hide", hidden); $("min").textContent = hidden ? "+" : "−"; });
  init();
})();
