import threading
import time
import requests
import logging
from pymongo import MongoClient
from datetime import datetime
import socket
import psutil  # Librería para monitoreo del sistema

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

# Obtener IP
def get_ip():
    return socket.gethostbyname(socket.gethostname())

# Obtener datos de Open Hardware Monitor
def get_hardware_data():
    try:
        response = requests.get(OHM_URL)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        print(f"Error obteniendo datos de Open Hardware Monitor: {e}")
        return None

# Extraer temperaturas de CPU/GPU
def extract_temperatures(data, target):
    temperatures = []

    def traverse_children(children):
        for item in children:
            if "Children" in item:
                traverse_children(item["Children"])
            if "Text" in item and target in item["Text"]:
                if "Value" in item and "°C" in str(item["Value"]):
                    try:
                        value = float(str(item["Value"]).replace(",", ".").replace("°C", "").strip())
                        temperatures.append({"name": item["Text"], "value": value})
                    except ValueError:
                        print(f"No se pudo convertir el valor: {item['Value']}")

    traverse_children(data.get("Children", []))
    return temperatures

# Monitorizar temperaturas y registrar alertas
def monitor_temperatures(target):
    while True:
        data = get_hardware_data()
        if data:
            temperatures = extract_temperatures(data, target)
            for temp in temperatures:
                if temp["value"] > 45:  # Umbral de 45°C
                    log_data(f"Alerta de temperatura alta: {temp['name']}", temp["value"])
        time.sleep(5)

# Monitorear utilización de memoria y tareas en ejecución
def monitor_memory_and_tasks():
    while True:
        memory_usage = psutil.virtual_memory().percent
        ip_address = get_ip()
        running_tasks = [p.info for p in psutil.process_iter(attrs=["pid", "name"])]
        
        # Registrar uso de memoria
        log_data("Utilización de memoria", f"{memory_usage}%", f"IP: {ip_address}")

        # Registrar tareas en ejecución
        tasks_log = f"Tareas en ejecución: {len(running_tasks)} procesos activos"
        log_data("Tareas en ejecución", tasks_log, f"IP: {ip_address}")

        time.sleep(10)

# Función para escribir en el log y MongoDB
def log_data(action, value, extra_info=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} - {action} - {value} - {extra_info}"

    # Escribir en el archivo log
    with log_lock:
        with open("activity.log", "a") as f:
            f.write(log_entry + "\n")
        with open("activity.log", "r") as f:
            lines = f.readlines()
        with open("activity.log", "w") as f:
            f.writelines(lines[-5:])

    # Guardar en MongoDB
    try:
        collection.insert_one(
            {"timestamp": timestamp, "action": action, "value": value, "extra_info": extra_info}
        )
    except Exception as e:
        print(f"Error guardando en MongoDB: {e}")

    # Enviar notificación a Telegram
    send_telegram_message(log_entry)

# Enviar mensaje a Telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=data)
        if response.status_code != 200:
            print(f"Error enviando mensaje a Telegram: {response.status_code}")
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")

# Crear hilos para CPU, GPU y monitor de memoria/tareas
threads = [
    threading.Thread(target=monitor_temperatures, args=("CPU",)),
    threading.Thread(target=monitor_temperatures, args=("GPU",)),
    threading.Thread(target=monitor_memory_and_tasks)
]

for thread in threads:
    thread.daemon = True
    thread.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Monitorización detenida.")