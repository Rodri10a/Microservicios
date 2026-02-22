# ═══════════════════════════════════════════════════════════════════════════════
# orders.py — Servicio de Pedidos  |  Puerto: 5002
# ═══════════════════════════════════════════════════════════════════════════════

import os
import jwt
import time
import datetime
from functools import wraps

import requests
from flask import Flask, jsonify, request
from database import get_db, init_db

app = Flask(__name__)

# ─── Configuración ────────────────────────────────────────────────────────────
SECRET_KEY             = os.getenv("SECRET_KEY",             "pinguino_secreto_2024")
INTERNAL_TOKEN         = os.getenv("INTERNAL_TOKEN",         "token_interno_servicios")
RESTAURANT_SERVICE_URL = os.getenv("RESTAURANT_SERVICE_URL", "http://localhost:5001")

ESTADOS_VALIDOS      = ["pending", "confirmed", "preparing", "ready", "cancelled"]
TRANSICIONES_VALIDAS = {
    "pending":   ["confirmed", "cancelled"],
    "confirmed": ["preparing", "cancelled"],
    "preparing": ["ready",     "cancelled"],
    "ready":     [],
    "cancelled": []
}