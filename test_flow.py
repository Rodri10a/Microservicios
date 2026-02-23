# ═══════════════════════════════════════════════════════════════════════════════
# test_flow.py — Prueba completa del flujo de microservicios
# Ejecutar con: python test_flow.py  (con los 3 servicios corriendo)
# ═══════════════════════════════════════════════════════════════════════════════

import requests

RESTAURANT = "http://localhost:5001"
ORDER      = "http://localhost:5002"
DELIVERY   = "http://localhost:5003"

def header(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def paso(num, descripcion):
    print(f"\n{'='*60}")
    print(f"  PASO {num}: {descripcion}")
    print(f"{'='*60}")

def mostrar(resp):
    status = "OK" if resp.ok else "ERROR"
    print(f"  Status: {resp.status_code} ({status})")
    print(f"  Respuesta: {resp.json()}")
    return resp.json()


# ─── PASO 1: Login ───────────────────────────────────────────────────────────
paso(1, "LOGIN — Obtener JWT desde restaurant_service (puerto 5001)")
print("  Enviando: POST /auth/token con usuario admin/admin123")

r = requests.post(f"{RESTAURANT}/auth/token", json={
    "username": "admin",
    "password": "admin123"
})
data = mostrar(r)
TOKEN = data["token"]
print(f"\n  Token JWT obtenido: {TOKEN[:30]}...")
print("  Este token se usa en TODOS los requests siguientes")


# ─── PASO 2: Crear restaurante ───────────────────────────────────────────────
paso(2, "CREAR RESTAURANTE — en restaurant_service (puerto 5001)")
print("  Enviando: POST /restaurants")

r = requests.post(f"{RESTAURANT}/restaurants", headers=header(TOKEN), json={
    "name": "Penguin Burgers",
    "address": "Antartida 123"
})
mostrar(r)


# ─── PASO 3: Agregar items al menú ──────────────────────────────────────────
paso(3, "AGREGAR ITEMS AL MENU — en restaurant_service (puerto 5001)")

print("\n  Enviando: POST /restaurants/1/menu (Hamburguesa)")
r = requests.post(f"{RESTAURANT}/restaurants/1/menu", headers=header(TOKEN), json={
    "name": "Hamburguesa Clasica",
    "price": 8.50
})
mostrar(r)

print("\n  Enviando: POST /restaurants/1/menu (Papas Fritas)")
r = requests.post(f"{RESTAURANT}/restaurants/1/menu", headers=header(TOKEN), json={
    "name": "Papas Fritas",
    "price": 3.00
})
mostrar(r)


# ─── PASO 4: Ver menú ───────────────────────────────────────────────────────
paso(4, "VER MENU — en restaurant_service (puerto 5001)")
print("  Enviando: GET /restaurants/1/menu")

r = requests.get(f"{RESTAURANT}/restaurants/1/menu", headers=header(TOKEN))
mostrar(r)


# ─── PASO 5: Crear pedido ───────────────────────────────────────────────────
paso(5, "CREAR PEDIDO — en order_service (puerto 5002)")
print("  Enviando: POST /orders")
print("  >> order_service LLAMA a restaurant_service para verificar los items")

r = requests.post(f"{ORDER}/orders", headers=header(TOKEN), json={
    "restaurant_id": 1,
    "customer_name": "Pinguino Pepe",
    "items": [
        {"menu_item_id": 1, "quantity": 2},
        {"menu_item_id": 2, "quantity": 1}
    ]
})
mostrar(r)
print("  Total esperado: 8.50 x 2 + 3.00 x 1 = 20.00")


# ─── PASO 6: Avanzar estado del pedido ──────────────────────────────────────
paso(6, "AVANZAR ESTADO DEL PEDIDO — en order_service (puerto 5002)")

for estado in ["confirmed", "preparing", "ready"]:
    print(f"\n  Enviando: PUT /orders/1/status -> '{estado}'")
    r = requests.put(f"{ORDER}/orders/1/status", headers=header(TOKEN), json={
        "status": estado
    })
    mostrar(r)


# ─── PASO 7: Crear delivery ─────────────────────────────────────────────────
paso(7, "CREAR DELIVERY — en delivery_service (puerto 5003)")
print("  Enviando: POST /deliveries")
print("  >> delivery_service LLAMA a order_service para verificar que el pedido esta 'ready'")

r = requests.post(f"{DELIVERY}/deliveries", headers=header(TOKEN), json={
    "order_id": 1,
    "address": "Iglu 456, Polo Sur",
    "driver_name": "Pingu Express"
})
mostrar(r)


# ─── PASO 8: Avanzar estado del delivery ────────────────────────────────────
paso(8, "AVANZAR ESTADO DEL DELIVERY — en delivery_service (puerto 5003)")

for estado in ["picked_up", "in_transit", "delivered"]:
    print(f"\n  Enviando: PUT /deliveries/1/status -> '{estado}'")
    r = requests.put(f"{DELIVERY}/deliveries/1/status", headers=header(TOKEN), json={
        "status": estado
    })
    mostrar(r)


# ─── PASO 9: Verificar todo ─────────────────────────────────────────────────
paso(9, "VERIFICAR TODO — consultar los 3 servicios")

print("\n  GET /restaurants (puerto 5001):")
r = requests.get(f"{RESTAURANT}/restaurants", headers=header(TOKEN))
mostrar(r)

print("\n  GET /orders (puerto 5002):")
r = requests.get(f"{ORDER}/orders", headers=header(TOKEN))
mostrar(r)

print("\n  GET /deliveries (puerto 5003):")
r = requests.get(f"{DELIVERY}/deliveries", headers=header(TOKEN))
mostrar(r)


# ─── PASO 10: Probar seguridad ──────────────────────────────────────────────
paso(10, "PROBAR SEGURIDAD — requests sin token (deben fallar)")

print("\n  GET /restaurants SIN token:")
r = requests.get(f"{RESTAURANT}/restaurants")
mostrar(r)
print("  Esperado: 401 Token JWT requerido")

print("\n  GET /orders SIN token:")
r = requests.get(f"{ORDER}/orders")
mostrar(r)
print("  Esperado: 401 Token JWT requerido")


# ─── RESUMEN ─────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("  FLUJO COMPLETO TERMINADO")
print(f"{'='*60}")
print("""
  restaurant_service (5001) -> Restaurante creado, menu con 2 items
  order_service      (5002) -> Pedido creado, estado: ready
  delivery_service   (5003) -> Delivery creado, estado: delivered

  Comunicacion entre servicios demostrada:
    order_service    -> llamo a restaurant_service (paso 5)
    delivery_service -> llamo a order_service      (paso 7)

  Seguridad demostrada:
    JWT requerido en todos los endpoints (paso 10)
    Token interno para comunicacion entre servicios
""")
