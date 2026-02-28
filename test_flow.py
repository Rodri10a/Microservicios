# test_flow.py — Cliente interactivo para probar los microservicios
# Ejecutar con: python test_flow.py  (con los 3 servicios corriendo)

import json
import requests

RESTAURANT_URL = "http://localhost:5001"
ORDER_URL      = "http://localhost:5002"
DELIVERY_URL   = "http://localhost:5003"
TOKEN = None


# --- Helpers ---

def make_headers():
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    return headers


def send_request(method, url, data=None):
    headers = make_headers()
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=3)
        elif method == "POST":
            resp = requests.post(url, headers=headers, data=json.dumps(data or {}), timeout=3)
        elif method == "PUT":
            resp = requests.put(url, headers=headers, data=json.dumps(data or {}), timeout=3)
        else:
            print(f"  Metodo HTTP no soportado: {method}")
            return None
    except requests.exceptions.ConnectionError:
        print(f"\n  [ERROR] No se pudo conectar a {url}")
        print("  Verifica que el microservicio correspondiente este levantado.")
        return None
    except requests.exceptions.Timeout:
        print(f"\n  [ERROR] Timeout al llamar a {url}")
        return None

    print(f"\n  [{resp.status_code}] {resp.json()}")
    return resp


# --- Restaurantes ---

def login():
    global TOKEN
    print("\n=== Login ===")
    username = input("  Usuario: ").strip()
    password = input("  Password: ").strip()
    resp = send_request("POST", f"{RESTAURANT_URL}/auth/token", {"username": username, "password": password})
    if resp and resp.status_code == 200:
        TOKEN = resp.json()["token"]
        print(f"  Token guardado correctamente")


def agregar_item_menu():
    print("\n=== Agregar item al menu ===")
    restaurant = input("  Nombre del restaurante: ").strip()
    name = input("  Nombre del item: ").strip()
    price = float(input("  Precio: ").strip())
    send_request("POST", f"{RESTAURANT_URL}/menu", {"restaurant_name": restaurant, "name": name, "price": price})


def ver_menu():
    print("\n=== Ver menu ===")
    restaurant = input("  Nombre del restaurante (enter para ver todo): ").strip()
    url = f"{RESTAURANT_URL}/menu"
    if restaurant:
        url += f"?restaurant={restaurant}"
    send_request("GET", url)


# --- Pedidos ---

def crear_pedido():
    print("\n=== Crear pedido ===")
    restaurant = input("  Nombre del restaurante: ").strip()
    customer = input("  Nombre del cliente: ").strip()
    items = []
    while True:
        mid = input("  ID del item del menu (enter para terminar): ").strip()
        if not mid:
            break
        qty = int(input("  Cantidad: ").strip())
        items.append({"menu_item_id": int(mid), "quantity": qty})
    if not items:
        print("  Pedido cancelado (sin items)")
        return
    send_request("POST", f"{ORDER_URL}/orders", {"restaurant_name": restaurant, "customer_name": customer, "items": items})


def actualizar_estado_pedido():
    print("\n=== Actualizar estado del pedido ===")
    oid = input("  ID del pedido: ").strip()
    print("  Estados: pending -> confirmed -> preparing -> ready (o cancelled)")
    status = input("  Nuevo estado: ").strip()
    send_request("PUT", f"{ORDER_URL}/orders/{oid}", {"status": status})


# --- Deliveries ---

def crear_delivery():
    print("\n=== Crear delivery ===")
    oid = input("  ID del pedido: ").strip()
    address = input("  Direccion de entrega: ").strip()
    send_request("POST", f"{DELIVERY_URL}/deliveries", {"order_id": int(oid), "address": address})


def actualizar_estado_delivery():
    print("\n=== Actualizar estado del delivery ===")
    did = input("  ID del delivery: ").strip()
    print("  Estados: assigned -> picked_up -> in_transit -> delivered (o failed)")
    status = input("  Nuevo estado: ").strip()
    send_request("PUT", f"{DELIVERY_URL}/deliveries/{did}", {"status": status})


# --- Menu principal ---

def main_menu():
    while True:
        print("\n=== CLIENTE MICROSERVICIOS ===")
        print("1) Login (obtener JWT)")
        print("2) Agregar item al menu")
        print("3) Ver menu")
        print("4) Crear pedido")
        print("5) Actualizar estado del pedido")
        print("6) Crear delivery")
        print("7) Actualizar estado del delivery")
        print("0) Salir")

        choice = input("\nOpcion: ").strip()

        if choice == "1":
            login()
        elif choice == "2":
            agregar_item_menu()
        elif choice == "3":
            ver_menu()
        elif choice == "4":
            crear_pedido()
        elif choice == "5":
            actualizar_estado_pedido()
        elif choice == "6":
            crear_delivery()
        elif choice == "7":
            actualizar_estado_delivery()
        elif choice == "0":
            print("Saliendo del cliente...")
            break
        else:
            print("Opcion invalida.")


if __name__ == "__main__":
    main_menu()
