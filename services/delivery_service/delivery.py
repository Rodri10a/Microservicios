# delivery.py — Servicio de Delivery | Puerto: 5003

import sys, os #  para poder importar common/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..")) # los dos .. significa la carpeta de arriba 

from flask import Flask, jsonify, request
from database import get_db, init_db
from common.auth import requiere_jwt 
from common.circuit_breaker import llamar_servicio

app = Flask(__name__)
ORDER_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:5002") 
# para ver si el pedido esta listo 


# Define que transiciones de estado son validas para un delivery
TRANSICIONES = {
    "assigned":   ["picked_up",  "failed"],
    "picked_up":  ["in_transit", "failed"],
    "in_transit": ["delivered",  "failed"],
    "delivered":  [], # ya no puede ir a ningun lado (fin)
    "failed":     [] # The same 
} 


# --- Endpoints (2) ---

# Crea un delivery: valida que el pedido exista y este en estado "ready"
# consultando al order_service, luego lo registra en la DB.
@app.route("/deliveries", methods=["POST"])
@requiere_jwt
def crear_delivery(): 
    # mando los datos necesarios ?
    datos = request.get_json()
    for campo in ["order_id", "address"]:
        if not datos or campo not in datos:
            return jsonify({"error": f"Falta '{campo}'"}), 400 # falta de datos 
        
    try:
        llamar_servicio(f"{ORDER_URL}/orders/{datos['order_id']}/ready", "order_service") # todo esta correcto 
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 422  # datos incorrectos
    
    except Exception as e:
        return jsonify({"error": str(e)}), 503 # circuit breaker abierto, servicio no disponible 

    with get_db() as conn:
        if conn.execute("SELECT id FROM deliveries WHERE order_id = ?", (datos["order_id"],)).fetchone():
            return jsonify({"error": f"Ya existe delivery para pedido {datos['order_id']}"}), 409 # conflicto 
        
        cur = conn.execute("INSERT INTO deliveries (order_id, address) VALUES (?, ?)",
                        (datos["order_id"], datos["address"]))
        conn.commit()
    return jsonify({"id": cur.lastrowid, "order_id": datos["order_id"],
                    "address": datos["address"], "status": "assigned"}), 201 # se creo un recurso 


# CAMBIA EL ESTADO de un DELIVERY siguiendo las transiciones permitidas.
# Parametro dinamico que viene de la URL 
@app.route("/deliveries/<int:did>", methods=["PUT"])
# int:oid =  indica que debe ser un valor entero 
@requiere_jwt
def actualizar_estado(did):
    with get_db() as conn:
        delivery = conn.execute("SELECT * FROM deliveries WHERE id = ?", (did,)).fetchone()
        
        
    if not delivery:
        return jsonify({"error": "Delivery no encontrado"}), 404 # not found 

    # proteccion contra None {}
    new = (request.get_json() or {}).get("status")
    if not new:
        return jsonify({"error": "Falta 'status'"}), 400 # falta datos 

    # verifica que se pasen las transiciones en orden 
    permitidos = TRANSICIONES.get(delivery["status"], [])
    if new not in permitidos:
        return jsonify({"error": f"No se puede pasar de '{delivery['status']}' a '{new}'", "allowed": permitidos}), 422 # datos incorrectos 

    with get_db() as conn:
        conn.execute("UPDATE deliveries SET status = ? WHERE id = ?", (new, did))# remplazan los valores de ? en la consulta 
        conn.commit()
    return jsonify({"id": did, "status": new})


if __name__ == "__main__":
    init_db()
    print("Delivery Service corriendo en http://localhost:5003")
    app.run(port=5003, debug=True, use_reloader=False) 
