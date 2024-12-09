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
client = MongoClient("mongodb://localhost:27017/")
db = client["monitoring"]
collection = db["logs"]

# Configuración de Telegram
TELEGRAM_BOT_TOKEN = "7380846438:AAG3zBi-k7D8CR-jEuuQMguKvGADQDLLLj0"
TELEGRAM_CHAT_ID = "7936967176"

# URL del servidor Open Hardware Monitor
OHM_URL = "http://localhost:8085/data.json"


# Función para obtener la dirección IP
def get_ip():
    return socket.gethostbyname(socket.gethostname())


# Función para obtener datos de Open Hardware Monitor
def get_hardware_data():
    try:
        response = requests.get(OHM_URL)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        print(f"Error obteniendo datos de Open Hardware Monitor: {e}")
        return None


# Función para obtener la temperatura de la CPU
def monitor_cpu():
    while True:
        data = get_hardware_data()
        if data:
            for hardware in data.get("Children", []):
                if hardware["Text"] == "CPU":
                    for sensor in hardware.get("Children", []):
                        if "Temperature" in sensor["Text"]:
                            temp = sensor["Value"]
                            if temp > 45:
                                log_data("Control de temperatura de la CPU", temp)
        time.sleep(5)


# Función para obtener la temperatura de la GPU
def monitor_gpu():
    while True:
        data = get_hardware_data()
        if data:
            for hardware in data.get("Children", []):
                if hardware["Text"] == "GPU":
                    for sensor in hardware.get("Children", []):
                        if "Temperature" in sensor["Text"]:
                            temp = sensor["Value"]
                            if temp > 45:
                                log_data("Control de temperatura de la GPU", temp)
        time.sleep(5)


# Función para registrar datos en el log, MongoDB y Telegram
def log_data(action, value):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ip_address = get_ip()
    log_entry = f"{timestamp} - {action} - Valor: {value}°C - IP: {ip_address}"

    # Escribir en el archivo log
    with log_lock:
        with open("activity.log", "a") as f:
            f.write(log_entry + "\n")

        # Limitar el archivo log a las últimas 5 entradas
        with open("activity.log", "r") as f:
            lines = f.readlines()
        with open("activity.log", "w") as f:
            f.writelines(lines[-5:])

    # Guardar en MongoDB
    collection.insert_one(
        {"timestamp": timestamp, "action": action, "value": value, "ip": ip_address}
    )

    # Enviar notificación por Telegram
    send_telegram_message(log_entry)


# Función para enviar un mensaje por Telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{7380846438:AAG3zBi-k7D8CR-jEuuQMguKvGADQDLLLj0}/sendMessage"
    data = {"chat_id": 7936967176, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")


# Crear y ejecutar hilos
threads = []
threads.append(threading.Thread(target=monitor_cpu))
threads.append(threading.Thread(target=monitor_gpu))

for thread in threads:
    thread.daemon = True
    thread.start()

# Mantener el programa corriendo
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Monitorización detenida.")
