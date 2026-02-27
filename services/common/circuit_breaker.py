import time
import logging
import requests as http_requests
from common.config import INTERNAL_TOKEN

logger = logging.getLogger(__name__)

circuito = {"fallos": 0, "estado": "closed", "abierto_desde": 0}


def llamar_servicio(url, servicio):
    if circuito["estado"] == "open":
        if time.time() - circuito["abierto_desde"] >= 30:
            circuito["estado"] = "half_open"
        else:
            raise Exception(f"{servicio} no disponible (circuit breaker abierto)")

    for intento in range(1, 4):
        try:
            resp = http_requests.get(url, headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"}, timeout=3)
            if resp.status_code in (404, 422):
                raise ValueError(resp.json().get("error", "Error en recurso"))
            resp.raise_for_status()
            circuito["fallos"], circuito["estado"] = 0, "closed"
            return resp.json()
        except ValueError:
            circuito["fallos"], circuito["estado"] = 0, "closed"
            raise
        except Exception as e:
            logger.warning(f"[{servicio}] Intento {intento}/3 fallo: {e}")
            if intento < 3:
                time.sleep(0.5 * intento)

    circuito["fallos"] += 1
    if circuito["fallos"] >= 3:
        circuito["estado"], circuito["abierto_desde"] = "open", time.time()
        logger.warning(f"[circuit_breaker] ABIERTO — pausando 30s")
    raise Exception(f"{servicio} no disponible")
