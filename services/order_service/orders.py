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

# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "order_service", "port": 5002}), 200


@app.route("/orders", methods=["POST"])
@requiere_jwt
def crear_pedido():
    """
    Crea un nuevo pedido.
    Flujo:
      1. Valida el body
      2. Para cada item llama a restaurant_service para verificar existencia y precio
      3. Calcula el total
      4. Guarda el pedido en la DB local

    Body:
        {
          "restaurant_id": int,
          "customer_name": str,
          "items": [
            { "menu_item_id": int, "quantity": int }
          ]
        }
    """
    datos = request.get_json()

    for campo in ["restaurant_id", "customer_name", "items"]:
        if not datos or campo not in datos:
            return jsonify({"error": f"Falta el campo '{campo}'"}), 400

    if not isinstance(datos["items"], list) or len(datos["items"]) == 0:
        return jsonify({"error": "El pedido debe tener al menos un item"}), 400

    # Verificar cada item en restaurant_service y calcular total
    items_verificados = []
    total = 0.0

    for item_req in datos["items"]:
        if "menu_item_id" not in item_req or "quantity" not in item_req:
            return jsonify({"error": "Cada item necesita 'menu_item_id' y 'quantity'"}), 400

        if item_req["quantity"] <= 0:
            return jsonify({"error": "La cantidad debe ser mayor a 0"}), 400

        try:
            menu_item = obtener_menu_item(item_req["menu_item_id"])
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 503

        subtotal = menu_item["price"] * item_req["quantity"]
        total   += subtotal

        items_verificados.append({
            "menu_item_id": item_req["menu_item_id"],
            "item_name":    menu_item["name"],
            "unit_price":   menu_item["price"],
            "quantity":     item_req["quantity"]
        })

    # Guardar en DB local
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO orders (restaurant_id, customer_name, total) VALUES (?, ?, ?)",
            (datos["restaurant_id"], datos["customer_name"], round(total, 2))
        )
        order_id = cursor.lastrowid

        for item in items_verificados:
            conn.execute(
                """INSERT INTO order_items
                (order_id, menu_item_id, item_name, unit_price, quantity)
                VALUES (?, ?, ?, ?, ?)""",
                (order_id, item["menu_item_id"], item["item_name"],
                item["unit_price"], item["quantity"])
            )
        conn.commit()

    app.logger.info(f"Pedido creado: id={order_id}, total={total}")

    return jsonify({
        "message": "Pedido creado",
        "order": {
            "id":            order_id,
            "restaurant_id": datos["restaurant_id"],
            "customer_name": datos["customer_name"],
            "status":        "pending",
            "total":         round(total, 2),
            "items":         items_verificados
        }
    }), 201