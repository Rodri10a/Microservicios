# restaurant.py — Servicio de Restaurantes | Puerto: 5001

import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jwt
from flask import Flask, jsonify, request
from database import get_db, init_db
from common.config import SECRET_KEY
from common.auth import requiere_jwt, requiere_token_interno

app = Flask(__name__)
DEMO_USER = {"username": "Rorro", "password": "rorro123", "role": "admin"}


# --- Endpoints (3) ---

@app.route("/auth/token", methods=["POST"])
def login():
    datos = request.get_json()
    if not datos or datos.get("username") != DEMO_USER["username"] or datos.get("password") != DEMO_USER["password"]:
        return jsonify({"error": "Credenciales incorrectas"}), 401
    token = jwt.encode({"username": datos["username"], "role": DEMO_USER["role"],
                        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)}, SECRET_KEY, algorithm="HS256")
    return jsonify({"token": token})


@app.route("/menu", methods=["GET", "POST"])
@requiere_jwt
def menu():
    if request.method == "GET":
        restaurant = request.args.get("restaurant")
        with get_db() as conn:
            if restaurant:
                items = conn.execute("SELECT * FROM menu_items WHERE restaurant_name = ?", (restaurant,)).fetchall()
            else:
                items = conn.execute("SELECT * FROM menu_items").fetchall()
        return jsonify({"menu": [dict(i) for i in items], "total": len(items)})

    datos = request.get_json()
    for campo in ["restaurant_name", "name", "price"]:
        if not datos or campo not in datos:
            return jsonify({"error": f"Falta '{campo}'"}), 400
    if datos["price"] <= 0:
        return jsonify({"error": "Precio debe ser > 0"}), 400
    with get_db() as conn:
        cur = conn.execute("INSERT INTO menu_items (restaurant_name, name, price) VALUES (?, ?, ?)",
                        (datos["restaurant_name"], datos["name"], datos["price"]))
        conn.commit()
    return jsonify({"id": cur.lastrowid, "restaurant_name": datos["restaurant_name"],
                    "name": datos["name"], "price": datos["price"]}), 201


@app.route("/menu-items/<int:item_id>")
@requiere_token_interno
def item_interno(item_id):
    with get_db() as conn:
        item = conn.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        return jsonify({"error": "Item no encontrado"}), 404
    return jsonify(dict(item))


if __name__ == "__main__":
    init_db()
    print("Restaurant Service corriendo en http://localhost:5001")
    app.run(port=5001, debug=True, use_reloader=False)
