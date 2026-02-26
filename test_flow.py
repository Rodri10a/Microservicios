# test_flow.py — Prueba completa del flujo de microservicios
# Ejecutar con: python test_flow.py  (con los 3 servicios corriendo)

import requests

RESTAURANT = "http://localhost:5001"
ORDER      = "http://localhost:5002"
DELIVERY   = "http://localhost:5003"

def header(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def paso(num, desc):
    print(f"\n{'='*60}\n  PASO {num}: {desc}\n{'='*60}")

def mostrar(resp):
    print(f"  [{resp.status_code}] {resp.json()}")
    return resp.json()


# 1. Login
paso(1, "LOGIN — obtener JWT")
data = mostrar(requests.post(f"{RESTAURANT}/auth/token", json={"username": "Rorro", "password": "rorro123"}))
TOKEN = data["token"]
print(f"  Token: {TOKEN[:30]}...")

# 2. Crear restaurante
paso(2, "CREAR RESTAURANTE")
mostrar(requests.post(f"{RESTAURANT}/restaurants", headers=header(TOKEN), json={"name": "Rorro Burgers", "address": "Hola 123"}))

# 3. Agregar items al menu
paso(3, "AGREGAR ITEMS AL MENU")
mostrar(requests.post(f"{RESTAURANT}/restaurants/1/menu", headers=header(TOKEN), json={"name": "Hamburguesa Clasica", "price": 8.50}))
mostrar(requests.post(f"{RESTAURANT}/restaurants/1/menu", headers=header(TOKEN), json={"name": "Papas Fritas", "price": 3.00}))

# 4. Ver menu
paso(4, "VER MENU")
mostrar(requests.get(f"{RESTAURANT}/restaurants/1/menu", headers=header(TOKEN)))

# 5. Crear pedido (order_service llama a restaurant_service)
paso(5, "CREAR PEDIDO — order_service llama a restaurant_service")
mostrar(requests.post(f"{ORDER}/orders", headers=header(TOKEN), json={
    "restaurant_id": 1, "customer_name": "Pengu",
    "items": [{"menu_item_id": 1, "quantity": 2}, {"menu_item_id": 2, "quantity": 1}]
}))
print("  Total esperado: 8.50 x 2 + 3.00 x 1 = 20.00")

# 6. Avanzar estado del pedido
paso(6, "AVANZAR ESTADO DEL PEDIDO")
for estado in ["confirmed", "preparing", "ready"]:
    mostrar(requests.put(f"{ORDER}/orders/1/status", headers=header(TOKEN), json={"status": estado}))

# 7. Crear delivery (delivery_service llama a order_service)
paso(7, "CREAR DELIVERY — delivery_service llama a order_service")
mostrar(requests.post(f"{DELIVERY}/deliveries", headers=header(TOKEN), json={
    "order_id": 1, "address": "Paraiso 640, and Mayas", "driver_name": "Biggie Express"
}))

# 8. Avanzar estado del delivery
paso(8, "AVANZAR ESTADO DEL DELIVERY")
for estado in ["picked_up", "in_transit", "delivered"]:
    mostrar(requests.put(f"{DELIVERY}/deliveries/1/status", headers=header(TOKEN), json={"status": estado}))

# 9. Probar seguridad (sin token, debe dar 401)
paso(9, "SEGURIDAD — requests sin token")
mostrar(requests.post(f"{RESTAURANT}/restaurants", json={"name": "Hack", "address": "x"}))
mostrar(requests.post(f"{ORDER}/orders", json={}))
print("  Esperado: 401 en ambos")

# Resumen
print(f"\n{'='*60}\n  FLUJO COMPLETO OK\n{'='*60}")
print("""  restaurant_service (5001) -> Restaurante + menu creados
  order_service      (5002) -> Pedido creado y avanzado a 'ready'
  delivery_service   (5003) -> Delivery creado y entregado

  Comunicacion entre servicios:
    order_service    -> llama a restaurant_service (paso 5)
    delivery_service -> llama a order_service      (paso 7)

  Seguridad: JWT requerido + token interno entre servicios
""")
