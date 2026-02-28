# test_auto.py — Ejecuta el flujo completo automaticamente
# Ejecutar con: python test_auto.py  (con los 3 servicios corriendo)

import requests

R = "http://localhost:5001"  # restaurant
O = "http://localhost:5002"  # orders
D = "http://localhost:5003"  # deliveries
S = {}  # session headers


def call(method, url, data=None):
    resp = requests.request(method, url, headers=S, json=data, timeout=5)
    print(f"  {method} {url} -> {resp.status_code} {resp.json()}")
    assert resp.ok, f"Fallo: {resp.json()}"
    return resp.json()


# 1. Login
print("\n--- Login ---")
token = call("POST", f"{R}/auth/token", {"username": "Rorro", "password": "rorro123"})["token"]
S["Authorization"] = f"Bearer {token}"

# 2. Agregar items al menu
print("\n--- Menu ---")
id1 = call("POST", f"{R}/menu", {"restaurant_name": "La Pizzeria", "name": "Pizza Margherita", "price": 12.50})["id"]
id2 = call("POST", f"{R}/menu", {"restaurant_name": "La Pizzeria", "name": "Pizza Pepperoni", "price": 14.00})["id"]
call("GET", f"{R}/menu?restaurant=La Pizzeria")

# 3. Crear pedido
print("\n--- Pedido ---")
order = call("POST", f"{O}/orders", {
    "restaurant_name": "La Pizzeria",
    "customer_name": "Juan Perez",
    "items": [{"menu_item_id": id1, "quantity": 2}, {"menu_item_id": id2, "quantity": 1}]
})

# 4. Avanzar pedido: pending -> confirmed -> preparing -> ready
for estado in ["confirmed", "preparing", "ready"]:
    call("PUT", f"{O}/orders/{order['id']}", {"status": estado})

# 5. Crear delivery y avanzar: assigned -> picked_up -> in_transit -> delivered
print("\n--- Delivery ---")
dlv = call("POST", f"{D}/deliveries", {"order_id": order["id"], "address": "Av. Siempre Viva 742"})
for estado in ["picked_up", "in_transit", "delivered"]:
    call("PUT", f"{D}/deliveries/{dlv['id']}", {"status": estado})

print(f"\n--- COMPLETADO: Pedido #{order['id']} (${order['total']}) entregado ---")
