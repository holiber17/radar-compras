/* Todas las llamadas a la API pasan por aquí: la página de Amazon nunca ve la sesión. */
const API = "https://radar-compras-six.vercel.app";

async function call(path, method, body) {
  const { token } = await chrome.storage.local.get("token");
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  let res;
  try {
    res = await fetch(API + path, { method: method || "GET", headers, body: body ? JSON.stringify(body) : undefined });
  } catch (e) {
    return { ok: false, status: 0, error: "Sin conexión con el servidor." };
  }
  let data = null;
  try { data = await res.json(); } catch (e) {}
  if (res.status === 401 && token && path !== "/login") await chrome.storage.local.remove("token");
  if (!res.ok) {
    const d = data && data.detail;
    return { ok: false, status: res.status, error: typeof d === "string" ? d : "No se pudo completar (" + res.status + ")." };
  }
  return { ok: true, status: res.status, data };
}

chrome.runtime.onMessage.addListener((msg, sender, send) => {
  (async () => {
    if (msg.type === "status") {
      const { token } = await chrome.storage.local.get("token");
      return { ok: true, data: { loggedIn: !!token } };
    }
    if (msg.type === "login") {
      const r = await call("/login", "POST", { correo: msg.correo, clave: msg.clave });
      if (r.ok) await chrome.storage.local.set({ token: r.data.token });
      return { ok: r.ok, error: r.error };
    }
    if (msg.type === "logout") { await chrome.storage.local.remove("token"); return { ok: true }; }
    if (msg.type === "api") {
      const allowed = ["/ajustes", "/productos"];
      if (!allowed.includes(msg.path) || !["GET", "POST"].includes(msg.method || "GET")) return { ok: false, error: "Solicitud no permitida." };
      return call(msg.path, msg.method, msg.body);
    }
    return { ok: false, error: "Mensaje desconocido." };
  })().then(send);
  return true;
});
