# restaurant.py — Servicio de Restaurantes | Puerto: 5001

import os, datetime
from functools import wraps
import jwt
from flask import Flask, jsonify, request
from database import get_db, init_db

app = Flask(__name__)
SECRET_KEY     = os.getenv("SECRET_KEY", "RorroArguello")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "token_interno")
DEMO_USER      = {"username": "Rorro", "password": "rorro123", "role": "admin"}


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


def requiere_token_interno(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        if token != INTERNAL_TOKEN:
            return jsonify({"error": "Acceso restringido a servicios internos"}), 403
        return f(*args, **kwargs)
    return decorador


# --- Endpoints (5) ---

@app.route("/auth/token", methods=["POST"])
def login():
    datos = request.get_json()
    if not datos or "username" not in datos or "password" not in datos:
        return jsonify({"error": "username y password son requeridos"}), 400
    if datos["username"] != DEMO_USER["username"] or datos["password"] != DEMO_USER["password"]:
        return jsonify({"error": "Credenciales incorrectas"}), 401

    token = jwt.encode({"username": datos["username"], "role": DEMO_USER["role"],
                         "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)}, SECRET_KEY, algorithm="HS256")
    return jsonify({"token": token, "expires_in": "8h"})


@app.route("/restaurants", methods=["POST"])
@requiere_jwt
def crear_restaurante():
    datos = request.get_json()
    for campo in ["name", "address"]:
        if not datos or campo not in datos:
            return jsonify({"error": f"Falta '{campo}'"}), 400

    with get_db() as conn:
        cur = conn.execute("INSERT INTO restaurants (name, address, phone) VALUES (?, ?, ?)",
                           (datos["name"], datos["address"], datos.get("phone", "")))
        conn.commit()
    return jsonify({"message": "Restaurante creado", "restaurant": {"id": cur.lastrowid, "name": datos["name"]}}), 201


@app.route("/restaurants/<int:rid>/menu", methods=["GET"])
@requiere_jwt
def ver_menu(rid):
    with get_db() as conn:
        if not conn.execute("SELECT id FROM restaurants WHERE id = ?", (rid,)).fetchone():
            return jsonify({"error": "Restaurante no encontrado"}), 404
        items = conn.execute("SELECT * FROM menu_items WHERE restaurant_id = ?", (rid,)).fetchall()
    return jsonify({"menu": [dict(i) for i in items], "total": len(items)})


@app.route("/restaurants/<int:rid>/menu", methods=["POST"])
@requiere_jwt
def agregar_item(rid):
    with get_db() as conn:
        if not conn.execute("SELECT id FROM restaurants WHERE id = ?", (rid,)).fetchone():
            return jsonify({"error": "Restaurante no encontrado"}), 404

    datos = request.get_json()
    for campo in ["name", "price"]:
        if not datos or campo not in datos:
            return jsonify({"error": f"Falta '{campo}'"}), 400
    if datos["price"] <= 0:
        return jsonify({"error": "El precio debe ser mayor a 0"}), 400

    with get_db() as conn:
        cur = conn.execute("INSERT INTO menu_items (restaurant_id, name, description, price) VALUES (?, ?, ?, ?)",
                        (rid, datos["name"], datos.get("description", ""), datos["price"]))
        conn.commit()
    return jsonify({"message": "Item agregado", "item": {"id": cur.lastrowid, "name": datos["name"], "price": datos["price"]}}), 201


@app.route("/menu-items/<int:item_id>")
@requiere_token_interno
def item_interno(item_id):
    with get_db() as conn:
        item = conn.execute("SELECT * FROM menu_items WHERE id = ? AND available = 1", (item_id,)).fetchone()
    if not item:
        return jsonify({"error": f"Item {item_id} no encontrado"}), 404
    return jsonify(dict(item))


if __name__ == "__main__":
    init_db()
    print("Restaurant Service corriendo en http://localhost:5001")
    app.run(port=5001, debug=True, use_reloader=False)
