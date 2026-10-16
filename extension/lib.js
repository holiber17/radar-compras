/* Funciones puras: se usan en la página de Amazon y en las pruebas. */
(function (root) {
  function extractAsin(url, doc) {
    var m = /\/(?:dp|gp\/product)\/([A-Z0-9]{10})(?:[/?#]|$)/i.exec(url || "");
    if (m) return m[1].toUpperCase();
    var el = doc && doc.getElementById && doc.getElementById("ASIN");
    return el && /^[A-Z0-9]{10}$/i.test(el.value || "") ? el.value.toUpperCase() : null;
  }
  function parsePrice(text) {
    var m = /\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)/.exec(text || "");
    return m ? parseFloat(m[1].replace(/,/g, "")) : null;
  }
  function evaluate(s, price, ship, venta) {
    var tax = price * s.tax / 100, total = price + tax + s.pack;
    var fee = venta * s.com / 100 + s.fijo, net = venta - fee - ship - total;
    var den = 1 - s.com / 100 - s.meta / 100;
    var mg = venta > 0 ? net / venta * 100 : 0;
    var verdict = mg >= s.meta ? "ok" : mg >= s.meta * 0.6 ? "mid" : "no";
    return { total: total, fee: fee, net: net, mg: mg, roi: total > 0 ? net / total * 100 : 0,
      minVenta: den > 0 ? (total + ship + s.fijo) / den : null, verdict: verdict };
  }
  var api = { extractAsin: extractAsin, parsePrice: parsePrice, evaluate: evaluate };
  if (typeof module !== "undefined") module.exports = api; else root.RadarLib = api;
})(this);
