const $ = (id) => document.getElementById(id);
const send = (m) => chrome.runtime.sendMessage(m);
async function show() {
  const r = await send({ type: "status" });
  $("login").hidden = r.data.loggedIn;
  $("ok").hidden = !r.data.loggedIn;
}
$("login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const correo = $("mail").value.trim(), clave = $("pass").value;
  if (!correo || clave.length < 10) { $("msg").textContent = "Escribe tu correo y tu contraseña (10 caracteres o más)."; return; }
  $("go").disabled = true; $("msg").textContent = "";
  const r = await send({ type: "login", correo, clave });
  $("go").disabled = false;
  if (!r.ok) { $("msg").textContent = r.error; return; }
  $("pass").value = ""; show();
});
$("out").addEventListener("click", async () => { await send({ type: "logout" }); show(); });
show();
