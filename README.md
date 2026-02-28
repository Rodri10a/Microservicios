# Microservicios - Sistema de Delivery de Comida

Sistema de microservicios con Flask que simula el flujo completo de un pedido de comida: desde crear un restaurante con su menu, realizar un pedido, hasta asignar un repartidor y completar la entrega.

## Arquitectura

```
                          JWT
  Postman ──────────────────────────────────────────────────────┐
     │                                                          │
     │         ┌──────────────────┐                             │
     ├────────>│ restaurant_service│ :5001                      │
     │         │  - Menu items    │                             │
     │         │  - Auth (JWT)    │<──────────┐                 │
     │         └──────────────────┘           │                 │
     │                                  token interno           │
     │         ┌──────────────────┐           │                 │
     ├────────>│  order_service   │ :5002     │                 │
     │         │  - Pedidos       │───────────┘                 │
     │         └──────────────────┘<──────────┐                 │
     │                                  token interno           │
     │         ┌──────────────────┐           │                 │
     └────────>│ delivery_service │ :5003     │                 │
               │  - Deliveries    │───────────┘                 │
               └──────────────────┘                             │
                                                                │
```

**Comunicacion entre servicios:**
- `order_service` llama a `restaurant_service` para verificar que los items del menu existen antes de crear un pedido
- `delivery_service` llama a `order_service` para verificar que el pedido esta en estado `ready` antes de asignar un repartidor
- Ambas comunicaciones usan un **circuit breaker** con retry (3 intentos) y backoff exponencial

## Tecnologias

- **Python 3** + **Flask** — framework web
- **SQLite** — base de datos independiente por servicio
- **PyJWT** — autenticacion con JSON Web Tokens
- **Requests** — comunicacion HTTP entre servicios

## Estructura del proyecto

```
Microservicios/
├── services/
│   ├── common/                    # Codigo compartido entre servicios
│   │   ├── __init__.py            # Hace que common sea un paquete Python
│   │   ├── config.py              # Constantes (SECRET_KEY, INTERNAL_TOKEN)
│   │   ├── auth.py                # Decoradores (requiere_jwt, requiere_token_interno)
│   │   └── circuit_breaker.py     # Retry + circuit breaker para llamadas entre servicios
│   ├── restaurant_service/
│   │   ├── restaurant.py          # Servicio principal (puerto 5001)
│   │   └── database.py            # DB: menu_items
│   ├── order_service/
│   │   ├── orders.py              # Servicio principal (puerto 5002)
│   │   └── database.py            # DB: orders (items como JSON)
│   └── delivery_service/
│       ├── delivery.py            # Servicio principal (puerto 5003)
│       └── database.py            # DB: deliveries
├── test_flow.py                   # Cliente interactivo para probar los servicios
├── requirements.txt
└── README.md
```

## Instalacion

```bash
# Clonar el repositorio
git clone https://github.com/Rodri10a/Microservicios.git
cd Microservicios

# Crear entorno virtual e instalar dependencias
python -m venv .venv
.venv\Scripts\Activate.ps1    # Windows PowerShell
pip install -r requirements.txt
```

## Levantar los servicios

Abrir 3 terminales (en cada una activar el venv):

```bash
# Terminal 1 — Restaurant Service
cd services/restaurant_service
python restaurant.py
```

```bash
# Terminal 2 — Order Service
cd services/order_service
python orders.py
```

```bash
# Terminal 3 — Delivery Service
cd services/delivery_service
python delivery.py
```

## Endpoints

### Restaurant Service (puerto 5001)

| Metodo | Endpoint | Auth | Descripcion |
|--------|----------|------|-------------|
| POST | `/auth/token` | No | Login, devuelve JWT |
| GET | `/menu` | JWT | Ver menu (filtrar con `?restaurant=nombre`) |
| POST | `/menu` | JWT | Agregar item al menu |

**Endpoint interno** (solo accesible entre servicios con token interno):
- `GET /menu-items/:id` — Devuelve un item del menu (usado por `order_service`)

### Order Service (puerto 5002)

| Metodo | Endpoint | Auth | Descripcion |
|--------|----------|------|-------------|
| POST | `/orders` | JWT | Crear pedido (valida items contra restaurant_service) |
| PUT | `/orders/:id` | JWT | Cambiar estado del pedido |

**Endpoint interno:**
- `GET /orders/:id/ready` — Verifica que el pedido este en estado `ready` (usado por `delivery_service`)

**Estados del pedido:**
```
pending → confirmed → preparing → ready
   ↓          ↓           ↓
cancelled  cancelled   cancelled
```

### Delivery Service (puerto 5003)

| Metodo | Endpoint | Auth | Descripcion |
|--------|----------|------|-------------|
| POST | `/deliveries` | JWT | Crear delivery (verifica pedido ready en order_service) |
| PUT | `/deliveries/:id` | JWT | Cambiar estado del delivery |

**Estados del delivery:**
```
assigned → picked_up → in_transit → delivered
   ↓          ↓           ↓
 failed     failed      failed
```

## Resiliencia: Circuit Breaker

La comunicacion entre servicios (`order_service` → `restaurant_service` y `delivery_service` → `order_service`) implementa un circuit breaker:

- **Retry**: 3 intentos con backoff exponencial (0.5s, 1s)
- **Circuit breaker**: despues de 3 fallos consecutivos, el circuito se abre y las llamadas fallan inmediatamente por 30 segundos
- **Half-open**: pasados los 30s, permite un intento de prueba para verificar si el servicio se recupero

## Flujo completo con Postman

### 1. Obtener token JWT
```
POST http://localhost:5001/auth/token
Body: { "username": "Rorro", "password": "rorro123" }
```
Copiar el token de la respuesta y usarlo en todos los requests siguientes como header:
```
Authorization: Bearer <token>
```

### 2. Agregar items al menu
```
POST http://localhost:5001/menu
Body: { "restaurant_name": "Rorro Burgers", "name": "Hamburguesa Clasica", "price": 8.50 }

POST http://localhost:5001/menu
Body: { "restaurant_name": "Rorro Burgers", "name": "Papas Fritas", "price": 3.00 }
```

### 3. Ver menu
```
GET http://localhost:5001/menu
GET http://localhost:5001/menu?restaurant=Rorro Burgers
```

### 4. Crear pedido
```
POST http://localhost:5002/orders
Body: {
  "restaurant_name": "Rorro Burgers",
  "customer_name": "Pengu",
  "items": [
    { "menu_item_id": 1, "quantity": 2 },
    { "menu_item_id": 2, "quantity": 1 }
  ]
}
```
Total esperado: 8.50 x 2 + 3.00 x 1 = 20.00

### 5. Avanzar estado del pedido hasta ready
```
PUT http://localhost:5002/orders/1
Body: { "status": "confirmed" }

PUT http://localhost:5002/orders/1
Body: { "status": "preparing" }

PUT http://localhost:5002/orders/1
Body: { "status": "ready" }
```

### 6. Crear delivery
```
POST http://localhost:5003/deliveries
Body: { "order_id": 1, "address": "Paraiso 640, and Mayas" }
```

### 7. Avanzar estado del delivery hasta delivered
```
PUT http://localhost:5003/deliveries/1
Body: { "status": "picked_up" }

PUT http://localhost:5003/deliveries/1
Body: { "status": "in_transit" }

PUT http://localhost:5003/deliveries/1
Body: { "status": "delivered" }
```

## Cliente interactivo (test_flow.py)

Con los 3 servicios corriendo, ejecutar:

```bash
python test_flow.py
```

Este script abre un menu interactivo con las siguientes opciones:
1. Login (obtener JWT)
2. Agregar item al menu
3. Ver menu
4. Crear pedido
5. Actualizar estado del pedido
6. Crear delivery
7. Actualizar estado del delivery

## Seguridad

- **JWT**: Todos los endpoints (excepto `/auth/token`) requieren un token JWT valido
- **Token interno**: La comunicacion entre servicios usa un token interno separado para que los endpoints internos no sean accesibles desde Postman
- **Validacion de transiciones**: Los estados solo pueden avanzar en orden valido (no se puede saltar estados ni retroceder)
- **Credenciales demo**: usuario `Rorro`, password `rorro123`
