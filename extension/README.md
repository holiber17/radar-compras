# Extensión Radar de Compras (Chrome)

## Instalar (modo desarrollador)
1. Descomprime la carpeta `extension`.
2. En Chrome abre `chrome://extensions` y activa **Modo de desarrollador**.
3. Pulsa **Cargar descomprimida** y elige la carpeta `extension`.
4. Pulsa el icono de la extensión, entra con tu correo y contraseña del Radar.
5. Abre un producto en amazon.com: aparece el panel abajo a la derecha.

## Qué hace
- Lee el ASIN, el título y el precio de la página que estás mirando. No consulta otras páginas ni sigue enlaces.
- Calcula ganancia y margen con tus costos guardados en el Radar.
- "Vigilar este producto" guarda el ASIN, el título y tus estimados en tu lista.

## Seguridad
La sesión se guarda en el almacenamiento de la extensión; la página de Amazon no la ve. Las llamadas a la API pasan por el proceso de fondo de la extensión.

## Pruebas
`node tests_extension/lib.test.js` (desde la raíz del repositorio).
