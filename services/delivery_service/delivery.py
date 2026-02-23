# ═══════════════════════════════════════════════════════════════════════════════
# delivery.py — Servicio de Delivery  |  Puerto: 5003
# ═══════════════════════════════════════════════════════════════════════════════

import os
import time
import logging
from functools import wraps
import jwt
import requests as http_requests
from flask import Flask, jsonify, request
from database import get_db, init_db

app = Flask(__name__)
logger = logging.getLogger(__name__)

# ─── Configuración ────────────────────────────────────────────────────────────
SECRET_KEY     = os.getenv("SECRET_KEY",     "pinguino_secreto_2024")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "token_interno_servicios")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:5002")


# ─── Auth ────────────────────────────────────────────────────────────────────

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


# ─── Service Client ──────────────────────────────────────────────────────────

def llamar_servicio(url: str, servicio: str) -> dict:
    def _llamar():
        resp = http_requests.get(
            url,
            headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
            timeout=3
        )
        if resp.status_code == 404:
            raise ValueError(resp.json().get("error", "Recurso no encontrado"))
        if resp.status_code == 422:
            raise ValueError(resp.json().get("error", "Validación fallida"))
        resp.raise_for_status()
        return resp.json()

    ultimo_error = None
    for intento in range(1, 4):
        try:
            return _llamar()
        except ValueError:
            raise
        except Exception as e:
            ultimo_error = e
            logger.warning(f"[{servicio}] Intento {intento}/3 falló: {e}")
            if intento < 3:
                time.sleep(0.5 * intento)

    logger.error(f"[{servicio}] Todos los reintentos fallaron: {ultimo_error}")
    raise Exception(f"{servicio} no disponible. Intentá más tarde.")

ESTADOS_VALIDOS = ["assigned", "picked_up", "in_transit", "delivered", "failed"]
TRANSICIONES_VALIDAS = {
    "assigned":   ["picked_up",  "failed"],
    "picked_up":  ["in_transit", "failed"],
    "in_transit": ["delivered",  "failed"],
    "delivered":  [],
    "failed":     []
}

# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "delivery_service", "port": 5003}), 200


@app.route("/deliveries", methods=["POST"])
@requiere_jwt
def crear_delivery():
    """
    Asigna un repartidor a un pedido listo.
    Flujo:
      1. Verifica que el pedido está en estado 'ready' (llama a order_service)
      2. Crea el registro de delivery en la DB local

    Body:
        {
          "order_id":    int,
          "address":     str,
          "driver_name": str?
        }
    """
    datos = request.get_json()

    for campo in ["order_id", "address"]:
        if not datos or campo not in datos:
            return jsonify({"error": f"Falta el campo '{campo}'"}), 400

    # Verificar en order_service que el pedido está listo
    try:
        pedido = llamar_servicio(
            f"{ORDER_SERVICE_URL}/orders/{datos['order_id']}/ready",
            "order_service"
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        return jsonify({"error": str(e)}), 503

    # Verificar que no exista ya un delivery para este pedido
    with get_db() as conn:
        existente = conn.execute(
            "SELECT id FROM deliveries WHERE order_id = ?", (datos["order_id"],)
        ).fetchone()

    if existente:
        return jsonify({"error": f"Ya existe un delivery para el pedido {datos['order_id']}"}), 409

    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO deliveries (order_id, customer_name, address, driver_name)
               VALUES (?, ?, ?, ?)""",
            (
                datos["order_id"],
                pedido["customer_name"],
                datos["address"],
                datos.get("driver_name", "Sin asignar")
            )
        )
        conn.commit()
        delivery_id = cursor.lastrowid

    app.logger.info(f"Delivery creado: id={delivery_id}, order_id={datos['order_id']}")

    return jsonify({
        "message":  "Delivery creado",
        "delivery": {
            "id":            delivery_id,
            "order_id":      datos["order_id"],
            "customer_name": pedido["customer_name"],
            "address":       datos["address"],
            "driver_name":   datos.get("driver_name", "Sin asignar"),
            "status":        "assigned"
        }
    }), 201


@app.route("/deliveries", methods=["GET"])
@requiere_jwt
def listar_deliveries():
    """
    Lista todos los deliveries.
    Query params: ?status=in_transit
    """
    status = request.args.get("status")
    query  = "SELECT * FROM deliveries WHERE 1=1"
    params = []

    if status:
        if status not in ESTADOS_VALIDOS:
            return jsonify({"error": f"Status inválido. Opciones: {ESTADOS_VALIDOS}"}), 400
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC"

    with get_db() as conn:
        deliveries = conn.execute(query, params).fetchall()

    return jsonify({"deliveries": [dict(d) for d in deliveries], "total": len(deliveries)}), 200


@app.route("/deliveries/<int:delivery_id>", methods=["GET"])
@requiere_jwt
def obtener_delivery(delivery_id):
    with get_db() as conn:
        delivery = conn.execute(
            "SELECT * FROM deliveries WHERE id = ?", (delivery_id,)
        ).fetchone()

    if not delivery:
        return jsonify({"error": "Delivery no encontrado"}), 404

    return jsonify(dict(delivery)), 200


@app.route("/deliveries/<int:delivery_id>/status", methods=["PUT"])
@requiere_jwt
def actualizar_estado(delivery_id):
    """
    Actualiza el estado del delivery.
    Transiciones válidas:
        assigned → picked_up | failed
        picked_up → in_transit | failed
        in_transit → delivered | failed
    Body: { "status": str }
    """
    with get_db() as conn:
        delivery = conn.execute(
            "SELECT * FROM deliveries WHERE id = ?", (delivery_id,)
        ).fetchone()

    if not delivery:
        return jsonify({"error": "Delivery no encontrado"}), 404

    datos      = request.get_json()
    new_status = datos.get("status") if datos else None

    if not new_status:
        return jsonify({"error": "El campo 'status' es requerido"}), 400

    if new_status not in ESTADOS_VALIDOS:
        return jsonify({"error": f"Status inválido. Opciones: {ESTADOS_VALIDOS}"}), 400

    current_status  = delivery["status"]
    transiciones_ok = TRANSICIONES_VALIDAS.get(current_status, [])

    if new_status not in transiciones_ok:
        return jsonify({
            "error":   f"No se puede pasar de '{current_status}' a '{new_status}'",
            "allowed": transiciones_ok
        }), 422

    with get_db() as conn:
        conn.execute(
            "UPDATE deliveries SET status=?, updated_at=datetime('now') WHERE id=?",
            (new_status, delivery_id)
        )
        conn.commit()

    app.logger.info(f"Delivery {delivery_id}: {current_status} → {new_status}")

    return jsonify({"message": f"Delivery actualizado a '{new_status}'"}), 200


@app.route("/deliveries/<int:delivery_id>", methods=["DELETE"])
@requiere_jwt
def cancelar_delivery(delivery_id):
    """Cancela un delivery si aún está en estado 'assigned'."""
    with get_db() as conn:
        delivery = conn.execute(
            "SELECT * FROM deliveries WHERE id = ?", (delivery_id,)
        ).fetchone()

    if not delivery:
        return jsonify({"error": "Delivery no encontrado"}), 404

    if delivery["status"] != "assigned":
        return jsonify({
            "error": f"Solo se puede cancelar en estado 'assigned' (actual: '{delivery['status']}')"
        }), 422

    with get_db() as conn:
        conn.execute(
            "UPDATE deliveries SET status='failed', updated_at=datetime('now') WHERE id=?",
            (delivery_id,)
        )
        conn.commit()

    return jsonify({"message": f"Delivery {delivery_id} cancelado"}), 200


# ─── Arranque ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("=" * 60)
    print("🚴 Delivery Service corriendo en http://localhost:5003")
    print("   POST /deliveries            → crear delivery")
    print("   GET  /deliveries            → listar deliveries")
    print("   PUT  /deliveries/:id/status → actualizar estado")
    print("=" * 60)
    app.run(port=5003, debug=True, use_reloader=False)
