import threading
import psutil
import datetime
import socket
from pymongo import MongoClient
from telegram import Bot
import asyncio
import wmi
import win32com.client
import time

# Configuración de MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["monitoring"]
collection = db["logs"]

# Configuración de Telegram
bot_token = "7760563991:AAFTxTb4ZQmkcvZsSb-5kSoXrOuG6ErhRx0"  # Reemplaza por tu token
chat_id = "6362273695"  # Reemplaza por tu chat ID
bot = Bot(token=bot_token)

# Archivo log (máximo 5 entradas)
log_file = "monitor.log"

# Inicialización de OpenHardwareMonitor (usando WMI para acceder a hardware)
hardware = wmi.WMI(namespace="root\\OpenHardwareMonitor")


def get_cpu_temperature():
    try:
        sensors = hardware.Sensor()
        for sensor in sensors:
            if (
                sensor.SensorType == "Temperature"
                and "CPU" in sensor.Name
                and sensor.Value is not None
            ):
                return float(sensor.Value)  # Convertimos el valor a float
        print("No se encontraron sensores de temperatura para la CPU.")
    except UnicodeDecodeError as e:
        print(f"Error de codificación en CPU: {e}")
    except Exception as e:
        print(f"Error obteniendo temperatura de CPU: {e}")
    return None


def get_gpu_temperature():
    try:
        sensors = hardware.Sensor()
        for sensor in sensors:
            if (
                sensor.SensorType == "Temperature"
                and "GPU" in sensor.Name
                and sensor.Value is not None
            ):
                return float(sensor.Value)  # Convertimos el valor a float
        print("No se encontraron sensores de temperatura para la GPU.")
    except UnicodeDecodeError as e:
        print(f"Error de codificación en GPU: {e}")
    except Exception as e:
        print(f"Error obteniendo temperatura de GPU: {e}")
    return None


def write_log(message):
    try:
        with open(log_file, "a", encoding="utf-8", errors="replace") as file:
            file.write(message + "\n")

        with open(log_file, "r", encoding="utf-8", errors="replace") as file:
            lines = file.readlines()

        # Mantener solo las últimas 5 líneas
        if len(lines) > 5:
            with open(log_file, "w", encoding="utf-8", errors="replace") as file:
                file.writelines(lines[-5:])
    except Exception as e:
        print(f"Error escribiendo en el log: {e}")


def log_to_db(data):
    try:
        collection.insert_one(data)
        if collection.count_documents({}) > 5000:
            oldest = collection.find().sort("_id", 1).limit(1)
            collection.delete_one({"_id": oldest[0]["_id"]})
    except Exception as e:
        print(f"Error registrando en la base de datos: {e}")


async def send_telegram_message(message):
    try:
        await bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")


def monitor():
    while True:
        try:
            # Capturar datos
            cpu_temp = get_cpu_temperature()
            gpu_temp = get_gpu_temperature()
            memory_usage = psutil.virtual_memory().percent
            ip_address = socket.gethostbyname(socket.gethostname())
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Verificar umbrales
            if cpu_temp and cpu_temp > 45:
                cpu_message = (
                    f"{timestamp} + Control de temperatura de la CPU + {ip_address}"
                )
                write_log(cpu_message)
                log_to_db(
                    {
                        "timestamp": timestamp,
                        "type": "CPU Temperature",
                        "ip": ip_address,
                        "value": cpu_temp,
                    }
                )
                asyncio.run(send_telegram_message(cpu_message))

            if gpu_temp and gpu_temp > 60:
                gpu_message = (
                    f"{timestamp} + Control de temperatura de la GPU + {ip_address}"
                )
                write_log(gpu_message)
                log_to_db(
                    {
                        "timestamp": timestamp,
                        "type": "GPU Temperature",
                        "ip": ip_address,
                        "value": gpu_temp,
                    }
                )
                asyncio.run(send_telegram_message(gpu_message))

            if memory_usage > 80:
                memory_message = f"{timestamp} + Utilización de memoria + {ip_address}"
                write_log(memory_message)
                log_to_db(
                    {
                        "timestamp": timestamp,
                        "type": "Memory Usage",
                        "ip": ip_address,
                        "value": memory_usage,
                    }
                )
                asyncio.run(send_telegram_message(memory_message))

            # Registrar tareas en ejecución
            tasks_message = f"{timestamp} + Tareas en ejecución: {[t.name for t in threading.enumerate()]}"
            write_log(tasks_message)
        except Exception as e:
            print(f"Error en monitor: {e}")
        time.sleep(5)  # Pausa para evitar sobrecargar el sistema


# Iniciar monitoreo
monitor_thread = threading.Thread(target=monitor, name="MonitorThread")
monitor_thread.start()
monitor_thread.join()
