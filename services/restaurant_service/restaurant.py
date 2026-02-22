# ═══════════════════════════════════════════════════════════════════════════════
# restaurant.py — Servicio de Restaurantes  |  Puerto: 5001
# ═══════════════════════════════════════════════════════════════════════════════

import os
import jwt
import time
import datetime
from functools import wraps

from flask import Flask, jsonify, request
from database import get_db, init_db

app = Flask(__name__)

# ─── Configuración ────────────────────────────────────────────────────────────
SECRET_KEY     = os.getenv("SECRET_KEY",     "pinguino_secreto_2024")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "token_interno_servicios")

DEMO_USER = {"username": "admin", "password": "admin123", "role": "admin"}

# ─── Utilidades de autenticación ──────────────────────────────────────────────

def crear_jwt(username: str, role: str) -> str:
    """Genera un JWT válido por 8 horas."""
    payload = {
        "username": username,
        "role":     role,
        "exp":      datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def requiere_jwt(f):
    """Decorador: valida que el header tenga un JWT válido."""
    @wraps(f)
    def decorador(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Token JWT requerido"}), 401
        try:
            payload = jwt.decode(auth.split(" ")[1], SECRET_KEY, algorithms=["HS256"])
            request.usuario_actual = payload
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado. Volvé a loguearte."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido. No pasás."}), 401
        return f(*args, **kwargs)
    return decorador


def requiere_token_interno(f):
    """Solo acepta requests de otros microservicios con INTERNAL_TOKEN."""
    @wraps(f)
    def decorador(*args, **kwargs):
        auth  = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        if token != INTERNAL_TOKEN:
            return jsonify({"error": "Acceso restringido a servicios internos"}), 403
        return f(*args, **kwargs)
    return decorador