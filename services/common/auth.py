
from functools import wraps  # con el wrap conservamos los datos originales  
import jwt 
from flask import jsonify, request # convierte a respuestas JSON, y el request contiene la informacion de la peticion HTTP 
from common.config import SECRET_KEY, INTERNAL_TOKEN

# Decorador que verifica si el cliente tiene un JWT valido
def requiere_jwt(f): 
    @wraps(f)  # es basicamente para que conserve los datos originales y no los modifique y asi 
    # se pueda cumplir con la funcion requiere JWT para saber si es un cliente o no es un cliente 
    def decorador(*args, **kwargs):
        ''' (*) empaqueta todo en una tupla, (**) sirve para empaquetar todo en un diccionario '''
        # *args: captura argumentos posicionales y  **kwargs: captura argumentos con nombre 
        auth = request.headers.get("Authorization", "")

        if not auth.startswith("Bearer "): 
            return jsonify({"error": "Token JWT requerido"}), 401  # 401 = No Autenticado 

        try: # ver si sigue bien la llave o expiro 
            request.usuario = jwt.decode(auth.split(" ")[1], SECRET_KEY, algorithms=["HS256"])

        # JWT expiro o es invalido 
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return jsonify({"error": "Token invalido o expirado"}), 401
        return f(*args, **kwargs)

    return decorador  # Retorna la funcion "mejorada" que reemplaza a la original

# Token Interno los usas los microservicios para conectarse, VERIFICA SERVICIOS 
def requiere_token_interno(f):  
    @wraps(f) 
    def decorador(*args, **kwargs):
        # .replace("Bearer ", "") quita el prefijo "Bearer " para obtener solo el token
        token = request.headers.get("Authorization", "").replace("Bearer ", "").strip() # elimina espacios en blanco
        if token != INTERNAL_TOKEN:
            return jsonify({"error": "Acceso restringido a servicios internos"}), 403  # 403 = Prohibido (Forbidden)
        return f(*args, **kwargs)
    return decorador  # Retorna la funcion protegida que reemplaza a la original
