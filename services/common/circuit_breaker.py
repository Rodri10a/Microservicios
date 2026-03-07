
import time
import logging
import requests as http_requests
from common.config import INTERNAL_TOKEN

logger = logging.getLogger(__name__)

# - estado: "closed" (normal), "open" (bloqueado), "half_open" (probando reconexion)
# - cada servicio tiene su propio circuito independiente
circuitos = {}

# Obtiene o crea el circuito para un servicio especifico
def _get_circuito(servicio):
    if servicio not in circuitos:
        circuitos[servicio] = {"fallos": 0, "estado": "closed", "abierto_desde": 0}
    return circuitos[servicio]

def llamar_servicio(url, servicio):
    circuito = _get_circuito(servicio)

    # Si el circuito esta abierto, verifica si ya pasaron 30s para probar reconexion
    if circuito["estado"] == "open":
        if time.time() - circuito["abierto_desde"] >= 30:
            circuito["estado"] = "half_open"
            logger.info(f"[circuit_breaker][{servicio}] HALF_OPEN — probando reconexion")
        else:
            raise Exception(f"{servicio} no disponible (circuit breaker abierto)")
            # raise es lanzar un error

    # RETRY 
    for intento in range(1, 4):
        try:
            # Hace la peticion GET con el token interno y un timeout de 3 segundos
            resp = http_requests.get(url, headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"}, timeout=3)

            # no cuentan como fallo del circuito (not found, invalid data)
            if resp.status_code in (404, 422):
                circuito["fallos"], circuito["estado"] = 0, "closed"
                raise ValueError(resp.json().get("error", "Error en recurso"))

            resp.raise_for_status() # Revisa el codigo HTTP y si es Error lanza una EXCEPTION

            # Exito reinicia el circuito
            circuito["fallos"], circuito["estado"] = 0, "closed"
            return resp.json()

        except ValueError:
            # Reinicia el circuito si agarro el 404 o 422
            raise

        except Exception as e:
            logger.warning(f"[{servicio}] Intento {intento}/3 fallo: {e}")
            if intento < 3:
                time.sleep(0.5 * intento) # espera incremental

    # CIRCUIT BREAKER 
    circuito["fallos"] += 1
    logger.warning(f"[circuit_breaker][{servicio}] Fallos acumulados: {circuito['fallos']}/3")

    # Si acumulo 3 fallos O estaba en half_open y fallo, abre el circuito
    if circuito["fallos"] >= 3 or circuito["estado"] == "half_open":
        circuito["estado"], circuito["abierto_desde"] = "open", time.time()
        circuito["fallos"] = 0
        logger.warning(f"[circuit_breaker][{servicio}] ABIERTO — pausando 30s")

    raise Exception(f"{servicio} no disponible")
