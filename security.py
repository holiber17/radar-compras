"""Contraseñas (scrypt, solo biblioteca estándar) y tokens (JWT)."""
import base64, hashlib, hmac, os, time
import jwt

N, R, P = 2**14, 8, 1


def hash_clave(clave: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(clave.encode(), salt=salt, n=N, r=R, p=P)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def verificar_clave(clave: str, guardado: str) -> bool:
    try:
        _, s, h = guardado.split("$")
        salt, esperado = base64.b64decode(s), base64.b64decode(h)
    except Exception:
        return False
    return hmac.compare_digest(hashlib.scrypt(clave.encode(), salt=salt, n=N, r=R, p=P), esperado)


def crear_token(user_id: str, secreto: str, horas: int = 24 * 14) -> str:
    return jwt.encode({"sub": user_id, "exp": int(time.time()) + horas * 3600}, secreto, algorithm="HS256")


def leer_token(token: str, secreto: str) -> str | None:
    try:
        return jwt.decode(token, secreto, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        return None
