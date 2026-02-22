# ═══════════════════════════════════════════════════════════════════════════════
# restaurant.py — Servicio de Restaurantes  |  Puerto: 5001
# ═══════════════════════════════════════════════════════════════════════════════

import os
import jwt
import time
import datetime
from functools import wraps

from flask import Flask, jsonify, request
from database import get_db, init_db

app = Flask(__name__)

# ─── Configuración ────────────────────────────────────────────────────────────
SECRET_KEY     = os.getenv("SECRET_KEY",     "pinguino_secreto_2024")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "token_interno_servicios")

DEMO_USER = {"username": "admin", "password": "admin123", "role": "admin"}

# ─── Utilidades de autenticación ──────────────────────────────────────────────

def crear_jwt(username: str, role: str) -> str:
    """Genera un JWT válido por 8 horas."""
    payload = {
        "username": username,
        "role":     role,
        "exp":      datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def requiere_jwt(f):
    """Decorador: valida que el header tenga un JWT válido."""
    @wraps(f)
    def decorador(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Token JWT requerido"}), 401
        try:
            payload = jwt.decode(auth.split(" ")[1], SECRET_KEY, algorithms=["HS256"])
            request.usuario_actual = payload
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado. Volvé a loguearte."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido. No pasás."}), 401
        return f(*args, **kwargs)
    return decorador


def requiere_token_interno(f):
    """Solo acepta requests de otros microservicios con INTERNAL_TOKEN."""
    @wraps(f)
    def decorador(*args, **kwargs):
        auth  = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        if token != INTERNAL_TOKEN:
            return jsonify({"error": "Acceso restringido a servicios internos"}), 403
        return f(*args, **kwargs)
    return decorador


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "restaurant_service", "port": 5001}), 200


# ── Autenticación ─────────────────────────────────────────────────────────────

@app.route("/auth/token", methods=["POST"])
def obtener_token():
    """
    Login: retorna un JWT si las credenciales son correctas.
    Body: { "username": "admin", "password": "admin123" }
    """
    datos = request.get_json()

    if not datos or "username" not in datos or "password" not in datos:
        return jsonify({"error": "username y password son requeridos"}), 400

    if datos["username"] != DEMO_USER["username"] or datos["password"] != DEMO_USER["password"]:
        return jsonify({"error": "Credenciales incorrectas"}), 401

    token = crear_jwt(datos["username"], DEMO_USER["role"])
    return jsonify({"token": token, "expires_in": "8h"}), 200


# ── Restaurantes ──────────────────────────────────────────────────────────────

@app.route("/restaurants", methods=["GET"])
@requiere_jwt
def listar_restaurantes():
    """Lista todos los restaurantes. Query params: ?is_open=1"""
    is_open = request.args.get("is_open", type=int)
    query   = "SELECT * FROM restaurants WHERE 1=1"
    params  = []

    if is_open is not None:
        query += " AND is_open = ?"
        params.append(is_open)

    with get_db() as conn:
        restaurants = conn.execute(query, params).fetchall()

    return jsonify({"restaurants": [dict(r) for r in restaurants], "total": len(restaurants)}), 200


@app.route("/restaurants/<int:restaurant_id>", methods=["GET"])
@requiere_jwt
def obtener_restaurante(restaurant_id):
    with get_db() as conn:
        restaurant = conn.execute(
            "SELECT * FROM restaurants WHERE id = ?", (restaurant_id,)
        ).fetchone()

    if not restaurant:
        return jsonify({"error": f"Restaurante {restaurant_id} no encontrado"}), 404

    return jsonify(dict(restaurant)), 200


@app.route("/restaurants", methods=["POST"])
@requiere_jwt
def crear_restaurante():
    """
    Crea un nuevo restaurante.
    Body: { "name": str, "address": str, "phone": str? }
    """
    datos = request.get_json()

    for campo in ["name", "address"]:
        if not datos or campo not in datos:
            return jsonify({"error": f"El campo '{campo}' es obligatorio"}), 400

    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO restaurants (name, address, phone) VALUES (?, ?, ?)",
            (datos["name"], datos["address"], datos.get("phone", ""))
        )
        conn.commit()
        restaurant_id = cursor.lastrowid

    return jsonify({
        "message":    "Restaurante creado",
        "restaurant": {"id": restaurant_id, "name": datos["name"], "address": datos["address"]}
    }), 201


@app.route("/restaurants/<int:restaurant_id>", methods=["PUT"])
@requiere_jwt
def actualizar_restaurante(restaurant_id):
    """Body (todos opcionales): { "name", "address", "phone", "is_open" }"""
    with get_db() as conn:
        restaurant = conn.execute(
            "SELECT * FROM restaurants WHERE id = ?", (restaurant_id,)
        ).fetchone()

    if not restaurant:
        return jsonify({"error": "Restaurante no encontrado"}), 404

    datos         = request.get_json() or {}
    nuevo_name    = datos.get("name",    restaurant["name"])
    nueva_address = datos.get("address", restaurant["address"])
    nuevo_phone   = datos.get("phone",   restaurant["phone"])
    nuevo_open    = datos.get("is_open", restaurant["is_open"])

    with get_db() as conn:
        conn.execute(
            "UPDATE restaurants SET name=?, address=?, phone=?, is_open=? WHERE id=?",
            (nuevo_name, nueva_address, nuevo_phone, nuevo_open, restaurant_id)
        )
        conn.commit()

    return jsonify({"message": "Restaurante actualizado"}), 200


@app.route("/restaurants/<int:restaurant_id>", methods=["DELETE"])
@requiere_jwt
def eliminar_restaurante(restaurant_id):
    with get_db() as conn:
        restaurant = conn.execute(
            "SELECT * FROM restaurants WHERE id = ?", (restaurant_id,)
        ).fetchone()

    if not restaurant:
        return jsonify({"error": "Restaurante no encontrado"}), 404

    with get_db() as conn:
        conn.execute("DELETE FROM menu_items  WHERE restaurant_id = ?", (restaurant_id,))
        conn.execute("DELETE FROM restaurants WHERE id = ?",            (restaurant_id,))
        conn.commit()

    return jsonify({"message": f"Restaurante {restaurant_id} eliminado"}), 200

