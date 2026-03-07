
import requests

R = "http://localhost:5001"  # restaurant
O = "http://localhost:5002"  # orders
D = "http://localhost:5003"  # deliveries
S = {}  # session headers
#

    # Hace las peticiones HTTP
def call(method, url, data=None):
    resp = requests.request(method, url, headers=S, json=data, timeout=5)
    print(f"  {method} {url} -> {resp.status_code} {resp.json()}")
    assert resp.ok, f"Fallo: {resp.json()}"
    # Verifica que la petición fue exitosa
    return resp.json()


# 1. Login
print("\n--- Login ---")
token = call("POST", f"{R}/auth/token", {"username": "Rorro", "password": "rorro123"})["token"]
S["Authorization"] = f"Bearer {token}"
# cargo a mi diccionario el header para no pasar devueta en todas las request 

# 2. Agregar items al menu
print("\n--- Menu ---")
id1 = call("POST", f"{R}/menu", {"restaurant_name": "la roca ", "name": "margarita", "price": 70000})["id"] # asignamos un id para cada restaurante creado
call("GET", f"{R}/menu?restaurant=la roca ")

# 3. Crear pedido
print("\n--- Pedido ---")
order = call("POST", f"{O}/orders", {
    "restaurant_name": "Rorro Burgers",
    "customer_name": "Rodrigo Arguello",
    "items": [{"menu_item_id": id1, "quantity": 4}] 
})

# 4. Avanzar pedido: pending -> confirmed -> preparing -> ready
for estado in ["confirmed", "preparing", "ready"]:
    call("PUT", f"{O}/orders/{order['id']}", {"status": estado})

# 5. Crear delivery y avanzar: assigned -> picked_up -> in_transit -> delivered
print("\n--- Delivery ---")
dlv = call("POST", f"{D}/deliveries", {"order_id": order["id"], "address": "Av.Sacramento 4516"})
for estado in ["picked_up", "in_transit", "delivered"]:
    call("PUT", f"{D}/deliveries/{dlv['id']}", {"status": estado})

print(f"\n--- COMPLETADO: Pedido #{order['id']} (${order['total']}) entregado ---")
