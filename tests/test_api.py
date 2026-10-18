import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["JWT_SECRET"] = "x" * 40
from fastapi.testclient import TestClient
import main, security


class T(unittest.TestCase):
    def test_clave(self):
        h = security.hash_clave("una-clave-larga-1")
        self.assertTrue(security.verificar_clave("una-clave-larga-1", h))
        self.assertFalse(security.verificar_clave("otra", h))
        self.assertFalse(security.verificar_clave("x", "basura"))

    def test_token(self):
        t = security.crear_token("u1", "s" * 40)
        self.assertEqual(security.leer_token(t, "s" * 40), "u1")
        self.assertIsNone(security.leer_token(t, "o" * 40))
        self.assertIsNone(security.leer_token("falso", "s" * 40))
        self.assertIsNone(security.leer_token(security.crear_token("u1", "s" * 40, horas=-1), "s" * 40))

    def test_rutas_exigen_sesion(self):
        c = TestClient(main.app)
        for m, p in [("get", "/productos"), ("get", "/compras"), ("get", "/ajustes"), ("delete", "/productos/B000000000")]:
            self.assertEqual(getattr(c, m)(p).status_code, 401, p)
        self.assertEqual(c.get("/productos", headers={"Authorization": "Bearer falso"}).status_code, 401)
        self.assertEqual(c.get("/salud").json(), {"ok": True})

    def test_validacion(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            main.Credenciales(correo="mal", clave="corta")
        main.Credenciales(correo="a@b.co", clave="una-clave-larga-1")
        self.assertIsNone(main.ASIN_RE.match("b000000000"))
        self.assertTrue(main.ASIN_RE.match("B00S0BEUIY"))

    def test_envios(self):
        sets, params = main.build_update({"estado": "Enviado", "guia": "9400", "user_id": "otro", "x; DROP": 1})
        self.assertEqual(sets, "estado=%s, guia=%s")
        self.assertEqual(params, ["Enviado", "9400"])
        with self.assertRaises(main.HTTPException):
            main._revisar_envio("Inventado")
        with self.assertRaises(main.HTTPException):
            main._revisar_envio("Pedido", "saliente")
        main._revisar_envio("Por enviar", "saliente")
        c = TestClient(main.app)
        for m_, p in [("get", "/envios"), ("post", "/envios"), ("patch", "/envios/1"), ("delete", "/envios/1")]:
            self.assertIn(getattr(c, m_)(p).status_code, (401, 422), p)


if __name__ == "__main__":
    unittest.main()
