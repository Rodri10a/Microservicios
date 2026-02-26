# delivery.py — Servicio de Delivery | Puerto: 5003

import os, time, logging
from functools import wraps
import jwt
import requests as http_requests
from flask import Flask, jsonify, request
from database import get_db, init_db

app = Flask(__name__)
logger = logging.getLogger(__name__)
SECRET_KEY     = os.getenv("SECRET_KEY", "RorroArguello")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "token_interno")
ORDER_URL      = os.getenv("ORDER_SERVICE_URL", "http://localhost:5002")

TRANSICIONES = {
    "assigned":   ["picked_up",  "failed"],
    "picked_up":  ["in_transit", "failed"],
    "in_transit": ["delivered",  "failed"],
    "delivered":  [],
    "failed":     []
}


def requiere_jwt(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Token JWT requerido"}), 401
        try:
            request.usuario = jwt.decode(auth.split(" ")[1], SECRET_KEY, algorithms=["HS256"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return jsonify({"error": "Token invalido o expirado"}), 401
        return f(*args, **kwargs)
    return decorador


# --- Circuit Breaker: falla inmediato despues de 3 fallos seguidos por 30s ---

circuito = {"fallos": 0, "estado": "closed", "abierto_desde": 0}

def llamar_servicio(url, servicio):
    if circuito["estado"] == "open":
        if time.time() - circuito["abierto_desde"] >= 30:
            circuito["estado"] = "half_open"
        else:
            raise Exception(f"{servicio} no disponible (circuit breaker abierto)")

    for intento in range(1, 4):
        try:
            resp = http_requests.get(url, headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"}, timeout=3)
            if resp.status_code in (404, 422):
                raise ValueError(resp.json().get("error", "Error en recurso"))
            resp.raise_for_status()
            circuito["fallos"], circuito["estado"] = 0, "closed"
            return resp.json()
        except ValueError:
            circuito["fallos"], circuito["estado"] = 0, "closed"
            raise
        except Exception as e:
            logger.warning(f"[{servicio}] Intento {intento}/3 fallo: {e}")
            if intento < 3:
                time.sleep(0.5 * intento)

    circuito["fallos"] += 1
    if circuito["fallos"] >= 3:
        circuito["estado"], circuito["abierto_desde"] = "open", time.time()
        logger.warning(f"[circuit_breaker] ABIERTO — pausando 30s")
    raise Exception(f"{servicio} no disponible")


# --- Endpoints (2) ---

@app.route("/deliveries", methods=["POST"])
@requiere_jwt
def crear_delivery():
    datos = request.get_json()
    for campo in ["order_id", "address"]:
        if not datos or campo not in datos:
            return jsonify({"error": f"Falta '{campo}'"}), 400

    try:
        pedido = llamar_servicio(f"{ORDER_URL}/orders/{datos['order_id']}/ready", "order_service")
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        return jsonify({"error": str(e)}), 503

    with get_db() as conn:
        if conn.execute("SELECT id FROM deliveries WHERE order_id = ?", (datos["order_id"],)).fetchone():
            return jsonify({"error": f"Ya existe delivery para pedido {datos['order_id']}"}), 409
        cur = conn.execute("INSERT INTO deliveries (order_id, customer_name, address, driver_name) VALUES (?, ?, ?, ?)",
                           (datos["order_id"], pedido["customer_name"], datos["address"], datos.get("driver_name", "Sin asignar")))
        conn.commit()

    return jsonify({"message": "Delivery creado", "delivery": {
        "id": cur.lastrowid, "order_id": datos["order_id"], "customer_name": pedido["customer_name"],
        "address": datos["address"], "driver_name": datos.get("driver_name", "Sin asignar"), "status": "assigned"
    }}), 201


@app.route("/deliveries/<int:did>/status", methods=["PUT"])
@requiere_jwt
def actualizar_estado(did):
    with get_db() as conn:
        delivery = conn.execute("SELECT * FROM deliveries WHERE id = ?", (did,)).fetchone()
    if not delivery:
        return jsonify({"error": "Delivery no encontrado"}), 404

    new = (request.get_json() or {}).get("status")
    if not new:
        return jsonify({"error": "El campo 'status' es requerido"}), 400

    permitidos = TRANSICIONES.get(delivery["status"], [])
    if new not in permitidos:
        return jsonify({"error": f"No se puede pasar de '{delivery['status']}' a '{new}'", "allowed": permitidos}), 422

    with get_db() as conn:
        conn.execute("UPDATE deliveries SET status=?, updated_at=datetime('now') WHERE id=?", (new, did))
        conn.commit()
    return jsonify({"message": f"Delivery actualizado a '{new}'"})


if __name__ == "__main__":
    init_db()
    print("Delivery Service corriendo en http://localhost:5003")
    app.run(port=5003, debug=True, use_reloader=False)
