# orders.py — Servicio de Pedidos | Puerto: 5002

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, jsonify, request
from database import get_db, init_db
from common.config import INTERNAL_TOKEN
from common.auth import requiere_jwt, requiere_token_interno
from common.circuit_breaker import llamar_servicio

app = Flask(__name__)
RESTAURANT_URL = os.getenv("RESTAURANT_SERVICE_URL", "http://localhost:5001")

TRANSICIONES = {
    "pending":   ["confirmed", "cancelled"],
    "confirmed": ["preparing", "cancelled"],
    "preparing": ["ready",     "cancelled"],
    "ready":     [],
    "cancelled": [] 
}


# --- Endpoints (3) ---

@app.route("/orders", methods=["POST"])
@requiere_jwt
def crear_pedido():
    datos = request.get_json()
    for campo in ["restaurant_id", "customer_name", "items"]:
        if not datos or campo not in datos:
            return jsonify({"error": f"Falta '{campo}'"}), 400
    if not isinstance(datos["items"], list) or not datos["items"]:
        return jsonify({"error": "El pedido debe tener al menos un item"}), 400

    items_ok, total = [], 0.0
    for it in datos["items"]:
        if "menu_item_id" not in it or "quantity" not in it or it["quantity"] <= 0:
            return jsonify({"error": "Cada item necesita 'menu_item_id' y 'quantity' > 0"}), 400
        try:
            mi = llamar_servicio(f"{RESTAURANT_URL}/menu-items/{it['menu_item_id']}", "restaurant_service")
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 503

        total += mi["price"] * it["quantity"]
        items_ok.append({"menu_item_id": it["menu_item_id"], "item_name": mi["name"], "unit_price": mi["price"], "quantity": it["quantity"]})

    with get_db() as conn:
        cur = conn.execute("INSERT INTO orders (restaurant_id, customer_name, total) VALUES (?, ?, ?)",
                        (datos["restaurant_id"], datos["customer_name"], round(total, 2)))
        order_id = cur.lastrowid
        for item in items_ok:
            conn.execute("INSERT INTO order_items (order_id, menu_item_id, item_name, unit_price, quantity) VALUES (?, ?, ?, ?, ?)",
                        (order_id, item["menu_item_id"], item["item_name"], item["unit_price"], item["quantity"]))
        conn.commit()

    return jsonify({"message": "Pedido creado", "order": {
        "id": order_id, "restaurant_id": datos["restaurant_id"], "customer_name": datos["customer_name"],
        "status": "pending", "total": round(total, 2), "items": items_ok
    }}), 201


@app.route("/orders/<int:oid>/status", methods=["PUT"])
@requiere_jwt
def actualizar_estado(oid):
    with get_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone()
    if not order:
        return jsonify({"error": "Pedido no encontrado"}), 404

    new = (request.get_json() or {}).get("status")
    if not new:
        return jsonify({"error": "El campo 'status' es requerido"}), 400

    permitidos = TRANSICIONES.get(order["status"], [])
    if new not in permitidos:
        return jsonify({"error": f"No se puede pasar de '{order['status']}' a '{new}'", "allowed": permitidos}), 422

    with get_db() as conn:
        conn.execute("UPDATE orders SET status=?, updated_at=datetime('now') WHERE id=?", (new, oid))
        conn.commit()
    return jsonify({"message": f"Pedido actualizado a '{new}'"})


@app.route("/orders/<int:oid>/ready")
@requiere_token_interno
def verificar_listo(oid):
    with get_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone()
    if not order:
        return jsonify({"error": "Pedido no encontrado"}), 404
    if order["status"] != "ready":
        return jsonify({"error": f"Pedido no listo (estado: '{order['status']}')"}), 422
    return jsonify({"order_id": order["id"], "customer_name": order["customer_name"],
                    "restaurant_id": order["restaurant_id"], "total": order["total"]})


if __name__ == "__main__":
    init_db()
    print("Order Service corriendo en http://localhost:5002")
    app.run(port=5002, debug=True, use_reloader=False)
