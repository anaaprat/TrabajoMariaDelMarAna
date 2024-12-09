import threading
import time
import requests
import logging
from pymongo import MongoClient
from datetime import datetime
import socket

# Configuración del log
logging.basicConfig(
    filename="activity.log", level=logging.INFO, format="%(asctime)s - %(message)s"
)
log_lock = threading.Lock()

# Configuración de MongoDB
try:
    client = MongoClient("mongodb://localhost:27017/")
    db = client["monitoring_db"]
    collection = db["logs"]
    print("Conexión a MongoDB exitosa")
except Exception as e:
    print(f"Error conectando a MongoDB: {e}")

# Configuración de Telegram
TELEGRAM_BOT_TOKEN = "7380846438:AAG3zBi-k7D8CR-jEuuQMguKvGADQDLLLj0"
TELEGRAM_CHAT_ID = "7936967176"

# URL del servidor Open Hardware Monitor
OHM_URL = "http://localhost:8085/data.json"


def get_ip():
    return socket.gethostbyname(socket.gethostname())


def get_hardware_data():
    try:
        response = requests.get(OHM_URL)
        response.raise_for_status()
        data = response.json()
        print("Datos obtenidos de Open Hardware Monitor:", data)  # Depuración
        return data
    except Exception as e:
        print(f"Error obteniendo datos de Open Hardware Monitor: {e}")
        return None


def extract_temperatures(data, target):
    """
    Extrae las temperaturas relevantes para un componente específico (CPU o GPU).
    """
    temperatures = []

    def traverse_children(children):
        for item in children:
            if "Children" in item:
                traverse_children(item["Children"])
            if "Text" in item and target in item["Text"]:
                if "Value" in item and "°C" in str(item["Value"]):  # Filtrar valores con °C
                    try:
                        # Reemplazar comas con puntos y convertir el valor a float
                        clean_value = float(str(item["Value"]).replace(",", ".").replace("°C", "").strip())
                        temperatures.append({"name": item["Text"], "value": clean_value})
                    except ValueError:
                        print(f"No se pudo convertir el valor: {item['Value']}")  # Depuración

    traverse_children(data.get("Children", []))
    return temperatures


def monitor_temperatures(target):
    """
    Monitorea temperaturas para CPU o GPU y registra alertas si superan el umbral.
    """
    print(f"Iniciando monitoreo para {target}")
    while True:
        data = get_hardware_data()
        if data:
            temperatures = extract_temperatures(data, target)
            print(f"Temperaturas detectadas para {target}: {temperatures}")
            for temp in temperatures:
                if temp["value"] > 45:  # Umbral de 45°C
                    log_data(f"Alerta de temperatura alta: {temp['name']}", temp["value"])
        time.sleep(5)



def log_data(action, value):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ip_address = get_ip()
    log_entry = f"{timestamp} - {action} - Valor: {value}°C - IP: {ip_address}"
    print("Registrando datos:", log_entry)  # Depuración

    with log_lock:
        with open("activity.log", "a") as f:
            f.write(log_entry + "\n")
        with open("activity.log", "r") as f:
            lines = f.readlines()
        with open("activity.log", "w") as f:
            f.writelines(lines[-5:])

    try:
        collection.insert_one(
            {"timestamp": timestamp, "action": action, "value": value, "ip": ip_address}
        )
    except Exception as e:
        print(f"Error guardando en MongoDB: {e}")

    send_telegram_message(log_entry)


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("Mensaje enviado a Telegram")
        else:
            print(f"Error enviando mensaje a Telegram: {response.status_code}")
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")

# Crear hilos para CPU y GPU
threads = []
threads.append(threading.Thread(target=monitor_temperatures, args=("CPU",)))
threads.append(threading.Thread(target=monitor_temperatures, args=("GPU",)))

for thread in threads:
    thread.daemon = True
    thread.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Monitorización detenida.")