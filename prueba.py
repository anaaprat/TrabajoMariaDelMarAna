import threading
import psutil
import datetime
import socket
from pymongo import MongoClient
from telegram import Bot

# Configuración de MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["monitoring"]
collection = db["logs"]

# Configuración de Telegram
bot_token = "7760563991:AAFTxTb4ZQmkcvZsSb-5kSoXrOuG6ErhRx0"
chat_id = "6362273695"
bot = Bot(token=bot_token)

# Archivo log (máximo 5 entradas)
log_file = "monitor.log"

def write_log(message):
    with open(log_file, "a") as file:
        file.write(message + "\n")

    with open(log_file, "r") as file:
        lines = file.readlines()

    # Mantener solo las últimas 5 líneas
    if len(lines) > 5:
        with open(log_file, "w") as file:
            file.writelines(lines[-5:])

def log_to_db(data):
    collection.insert_one(data)
    if collection.count_documents({}) > 5000:
        # Eliminar entradas más antiguas si exceden 5000
        oldest = collection.find().sort("_id", 1).limit(1)
        collection.delete_one({"_id": oldest[0]["_id"]})

def monitor_temperature():
    while True:
        temp = psutil.sensors_temperatures().get('coretemp', [])[0].current
        if temp > 45:
            ip_address = socket.gethostbyname(socket.gethostname())
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"{timestamp} + Control de temperatura de la CPU + {ip_address}"

            write_log(message)
            log_to_db({"timestamp": timestamp, "type": "CPU Temperature", "ip": ip_address, "value": temp})
            bot.send_message(chat_id, message)

def monitor_gpu():
    # Implementar para GPU si tienes librerías específicas
    pass

def monitor_memory():
    while True:
        memory = psutil.virtual_memory().percent
        if memory > 80:  # Por ejemplo, un umbral
            ip_address = socket.gethostbyname(socket.gethostname())
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"{timestamp} + Utilización de memoria + {ip_address}"

            write_log(message)
            log_to_db({"timestamp": timestamp, "type": "Memory Usage", "ip": ip_address, "value": memory})
            bot.send_message(chat_id, message)

# Crear hilos
cpu_thread = threading.Thread(target=monitor_temperature)
memory_thread = threading.Thread(target=monitor_memory)

# Iniciar hilos
cpu_thread.start()
memory_thread.start()

# Asegurarse de que los hilos no se cierren
cpu_thread.join()
memory_thread.join()
