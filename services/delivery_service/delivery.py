# delivery.py — Servicio de Delivery | Puerto: 5003

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, jsonify, request
from database import get_db, init_db
from common.auth import requiere_jwt
from common.circuit_breaker import llamar_servicio

app = Flask(__name__)
ORDER_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:5002")

TRANSICIONES = {
    "assigned":   ["picked_up",  "failed"],
    "picked_up":  ["in_transit", "failed"],
    "in_transit": ["delivered",  "failed"],
    "delivered":  [],
    "failed":     []
} 


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
