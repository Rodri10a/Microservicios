from functools import wraps
import jwt
from flask import jsonify, request
from common.config import SECRET_KEY, INTERNAL_TOKEN


def requiere_jwt(f):
    @wraps(f)
    
    def decorador(*parametros_ruta, **parametros_ruta_nombrados):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Token JWT requerido"}), 401
        try:
            request.usuario = jwt.decode(auth.split(" ")[1], SECRET_KEY, algorithms=["HS256"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return jsonify({"error": "Token invalido o expirado"}), 401
        return f(*parametros_ruta, **parametros_ruta_nombrados)
    return decorador


def requiere_token_interno(f):
    @wraps(f)
    def decorador(*parametros_ruta, **parametros_ruta_nombrados):
        token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        if token != INTERNAL_TOKEN:
            return jsonify({"error": "Acceso restringido a servicios internos"}), 403
        return f(*parametros_ruta, **parametros_ruta_nombrados)
    return decorador
