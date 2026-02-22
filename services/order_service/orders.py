# ═══════════════════════════════════════════════════════════════════════════════
# orders.py — Servicio de Pedidos  |  Puerto: 5002
# ═══════════════════════════════════════════════════════════════════════════════

import os
import jwt
import time
import datetime
from functools import wraps

import requests
from flask import Flask, jsonify, request
from database import get_db, init_db

app = Flask(__name__)

# ─── Configuración ────────────────────────────────────────────────────────────
SECRET_KEY             = os.getenv("SECRET_KEY",             "pinguino_secreto_2024")
INTERNAL_TOKEN         = os.getenv("INTERNAL_TOKEN",         "token_interno_servicios")
RESTAURANT_SERVICE_URL = os.getenv("RESTAURANT_SERVICE_URL", "http://localhost:5001")

ESTADOS_VALIDOS      = ["pending", "confirmed", "preparing", "ready", "cancelled"]
TRANSICIONES_VALIDAS = {
    "pending":   ["confirmed", "cancelled"],
    "confirmed": ["preparing", "cancelled"],
    "preparing": ["ready",     "cancelled"],
    "ready":     [],
    "cancelled": []
}


# ─── Autenticación ────────────────────────────────────────────────────────────

def requiere_jwt(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Token JWT requerido"}), 401
        try:
            payload = jwt.decode(auth.split(" ")[1], SECRET_KEY, algorithms=["HS256"])
            request.usuario_actual = payload
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401
        return f(*args, **kwargs)
    return decorador


def requiere_token_interno(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        auth  = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        if token != INTERNAL_TOKEN:
            return jsonify({"error": "Acceso restringido a servicios internos"}), 403
        return f(*args, **kwargs)
    return decorador


# ─── Comunicación con restaurant_service ──────────────────────────────────────

def obtener_menu_item(item_id: int) -> dict:
    """
    Llama a restaurant_service para verificar que el item existe.
    Implementa retry con backoff para resiliencia.
    """
    def _llamar():
        resp = requests.get(
            f"{RESTAURANT_SERVICE_URL}/menu-items/{item_id}",
            headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
            timeout=3
        )
        if resp.status_code == 404:
            raise ValueError(f"Item de menú {item_id} no existe o no está disponible")
        resp.raise_for_status()
        return resp.json()

    ultimo_error = None
    for intento in range(1, 4):
        try:
            return _llamar()
        except ValueError as e:
            raise e
        except Exception as e:
            ultimo_error = e
            app.logger.warning(f"[restaurant_service] Intento {intento}/3 falló: {e}")
            if intento < 3:
                time.sleep(0.5 * intento)

    app.logger.error(f"[restaurant_service] Todos los reintentos fallaron: {ultimo_error}")
    raise Exception("restaurant_service no disponible. Intentá más tarde.") 

