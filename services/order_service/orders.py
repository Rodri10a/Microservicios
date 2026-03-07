# orders.py — Servicio de Pedidos | Puerto: 5002

import sys, os, json # para poder importar common/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..")) # los dos .. significa la carpeta de arriba 


from flask import Flask, jsonify, request
from database import get_db, init_db
from common.auth import requiere_jwt, requiere_token_interno 
from common.circuit_breaker import llamar_servicio

app = Flask(__name__)
# URL del restaurant_service para validar que los items del menu existen
RESTAURANT_URL = os.getenv("RESTAURANT_SERVICE_URL", "http://localhost:5001")

# Define que transiciones de estado son validas para un pedido
TRANSICIONES = {
    "pending":   ["confirmed", "cancelled"],
    "confirmed": ["preparing", "cancelled"],
    "preparing": ["ready",     "cancelled"],
    "ready":     [],
    "cancelled": []
}


# --- Endpoints (3) ---

# Crea un pedido: valida cada item contra el restaurant_service,
# calcula el total y guarda todo en la DB.
@app.route("/orders", methods=["POST"])
@requiere_jwt
def crear_pedido():
    datos = request.get_json()
    for campo in ["restaurant_name", "customer_name", "items"]:
        if not datos or campo not in datos:
            return jsonify({"error": f"Falta '{campo}'"}), 400 # faltan datos 
        
    # Para saber si es una lista, y para saber si esta vacia 
    # para validarnos que cree un pedido y tenga un item
    if not isinstance(datos["items"], list) or not datos["items"]:
        return jsonify({"error": "El pedido debe tener al menos un item"}), 400

    items_ok, total = [], 0.0
    for it in datos["items"]:
        if "menu_item_id" not in it or "quantity" not in it or it["quantity"] <= 0:
            return jsonify({"error": "Cada item necesita 'menu_item_id' y 'quantity' > 0"}), 400 # faltan datos 
        
        try:
            mi = llamar_servicio(f"{RESTAURANT_URL}/menu-items/{it['menu_item_id']}", "restaurant_service")
            # Se comprueba que exista 
            
        except ValueError as e:
            return jsonify({"error": str(e)}), 404 # not found 
        
        except Exception as e:
            return jsonify({"error": str(e)}), 503 # servicio no disponible 
        
        # calcula el total y guarda los items validos
        total += mi["price"] * it["quantity"]
        items_ok.append({"menu_item_id": it["menu_item_id"], "name": mi["name"], "price": mi["price"], "quantity": it["quantity"]})

    with get_db() as conn:
        cur = conn.execute("INSERT INTO orders (restaurant_name, customer_name, total, items) VALUES (?, ?, ?, ?)",
                        (datos["restaurant_name"], datos["customer_name"], round(total, 2), json.dumps(items_ok))) # json.dumps convierte una lista a diccionario
        conn.commit()
    return jsonify({"id": cur.lastrowid, "restaurant_name": datos["restaurant_name"],
                    "customer_name": datos["customer_name"], "status": "pending",
                    "total": round(total, 2), "items": items_ok}), 201 # se creo un recurso 


# CAMBIA LOS ESTADOS DE UN PEDIDO siguiendo las transiciones permitidas.
@app.route("/orders/<int:oid>", methods=["PUT"])
# int:oid =  indica que debe ser un valor entero 

@requiere_jwt
def actualizar_estado(oid):
    with get_db() as conn:   # , crea una tupla, porque ? necesita una tupla aunque sea solo un parametro
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone() 
    if not order:
        return jsonify({"error": "Pedido no encontrado"}), 404

    # valida nuevo estado, proteccion contra None {}
    new = (request.get_json() or {}).get("status")
    if not new:
        return jsonify({"error": "Falta 'status'"}), 400 # faltan datos 

    # validar la transicion 
    permitidos = TRANSICIONES.get(order["status"], [])
    if new not in permitidos:
        return jsonify({"error": f"No se puede pasar de '{order['status']}' a '{new}'", "allowed": permitidos}), 422 # datos invalidos 

    with get_db() as conn:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (new, oid))
        conn.commit()
    return jsonify({"id": oid, "status": new})


# Endpoint interno: verifica que el pedido este en estado "ready".
# Usado por delivery_service antes de crear un delivery.
@app.route("/orders/<int:oid>/ready")
@requiere_token_interno 
def verificar_listo(oid):
    with get_db() as conn: 
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone() 
        
    if not order:
        return jsonify({"error": "Pedido no encontrado"}), 404
    
    if order["status"] != "ready":
        return jsonify({"error": f"Pedido no listo (estado: '{order['status']}')"}), 422 # datos invalidos 
    return jsonify({"order_id": order["id"], "customer_name": order["customer_name"]})
    


if __name__ == "__main__":
    init_db()
    print("Order Service corriendo en http://localhost:5002")
    app.run(port=5002, debug=True, use_reloader=False)
