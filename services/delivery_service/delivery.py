# ═══════════════════════════════════════════════════════════════════════════════
# delivery.py — Servicio de Delivery  |  Puerto: 5003
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
SECRET_KEY        = os.getenv("SECRET_KEY",        "pinguino_secreto_2024")
INTERNAL_TOKEN    = os.getenv("INTERNAL_TOKEN",    "token_interno_servicios")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:5002")

ESTADOS_VALIDOS      = ["assigned", "picked_up", "in_transit", "delivered", "failed"]
TRANSICIONES_VALIDAS = {
    "assigned":   ["picked_up",  "failed"],
    "picked_up":  ["in_transit", "failed"],
    "in_transit": ["delivered",  "failed"],
    "delivered":  [],
    "failed":     []
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


# ─── Comunicación con order_service ───────────────────────────────────────────

def verificar_pedido_listo(order_id: int) -> dict:
    """
    Llama a order_service para confirmar que el pedido está en estado 'ready'.
    Implementa retry con backoff para resiliencia.
    """
    def _llamar():
        resp = requests.get(
            f"{ORDER_SERVICE_URL}/orders/{order_id}/ready",
            headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
            timeout=3
        )
        if resp.status_code == 404:
            raise ValueError(f"Pedido {order_id} no encontrado")
        if resp.status_code == 422:
            data = resp.json()
            raise ValueError(data.get("error", "El pedido no está listo"))
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
            app.logger.warning(f"[order_service] Intento {intento}/3 falló: {e}")
            if intento < 3:
                time.sleep(0.5 * intento)

    app.logger.error(f"[order_service] Todos los reintentos fallaron: {ultimo_error}")
    raise Exception("order_service no disponible. Intentá más tarde.")

