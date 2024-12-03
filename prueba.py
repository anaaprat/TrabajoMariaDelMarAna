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
hardware = wmi.WMI(namespace="root\OpenHardwareMonitor")


def get_sensors():
    try:
        wmi = win32com.client.GetObject("winmgmts:\\\\.\\root\\OpenHardwareMonitor")
        sensors = wmi.ExecQuery("SELECT * FROM Sensor")
        for sensor in sensors:
            if sensor.SensorType == "Temperature" and sensor.Value is not None:
                print(f"{sensor.Name}: {sensor.Value} °C")
    except Exception as e:
        print(f"Error al obtener datos de hardware: {e}")


get_sensors()


def monitor_temperature():
    try:
        wmi = win32com.client.GetObject("winmgmts:\\\\.\\root\\OpenHardwareMonitor")
        sensors = wmi.ExecQuery("SELECT * FROM Sensor WHERE SensorType='Temperature'")
        if not sensors:
            print("No se encontraron sensores de temperatura disponibles.")
            return
        for sensor in sensors:
            if "CPU" in sensor.Name:
                print(f"{sensor.Name}: {sensor.Value} °C")
    except Exception as e:
        print(f"Error obteniendo temperatura de la CPU: {e}")


def get_cpu_temperature():
    try:
        sensors = hardware.Sensor()
        for sensor in sensors:
            if (
                sensor.SensorType == "Temperature"
                and "CPU" in sensor.Name
                and sensor.Value is not None
            ):
                return sensor.Value
        print("No se encontraron sensores de temperatura para la CPU.")
    except Exception as e:
        print(f"Error obteniendo temperatura de CPU: {e}")
    return None


def get_gpu_temperature():
    try:
        sensors = hardware.Sensor()
        # Recorremos los sensores disponibles
        for sensor in sensors:
            # Validamos si el sensor es de tipo temperatura y pertenece a la GPU
            if (
                sensor.SensorType == "Temperature"
                and "GPU" in sensor.Name
                and sensor.Value is not None
            ):
                return sensor.Value  # Devolvemos la temperatura si es válida
        print("No se encontraron sensores de temperatura para la GPU.")
    except Exception as e:
        print(f"Error obteniendo temperatura de GPU: {e}")
    return None  # Devolvemos None si no hay datos disponibles


def write_log(message):
    with open(log_file, "a", encoding="utf-8") as file:
        file.write(message + "\n")

    with open(log_file, "r", encoding="utf-8") as file:
        lines = file.readlines()

    # Mantener solo las últimas 5 líneas
    if len(lines) > 5:
        with open(log_file, "w", encoding="utf-8") as file:
            file.writelines(lines[-5:])


def log_to_db(data):
    collection.insert_one(data)
    if collection.count_documents({}) > 5000:
        # Eliminar entradas más antiguas si exceden 5000
        oldest = collection.find().sort("_id", 1).limit(1)
        collection.delete_one({"_id": oldest[0]["_id"]})


async def send_telegram_message(message):
    await bot.send_message(chat_id=chat_id, text=message)


def monitor_temperature():
    while True:
        try:
            temp = get_cpu_temperature()
            if temp is None:  # Si no se puede obtener la temperatura
                print("No se encontró un sensor válido para la CPU. Reintentando...")
                time.sleep(5)  # Espera 5 segundos antes de reintentar
                continue
            if temp > 45:  # Umbral de temperatura
                ip_address = socket.gethostbyname(socket.gethostname())
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                message = (
                    f"{timestamp} + Control de temperatura de la CPU + {ip_address}"
                )

                write_log(message)
                log_to_db(
                    {
                        "timestamp": timestamp,
                        "type": "CPU Temperature",
                        "ip": ip_address,
                        "value": temp,
                    }
                )
                asyncio.run(send_telegram_message(message))
        except Exception as e:
            print(f"Error en monitor_temperature: {e}")
        time.sleep(5)  # Pausa para evitar sobrecargar el sistema


def monitor_gpu():
    while True:
        try:
            temp = get_gpu_temperature()
            if temp is None:  # Si no se puede obtener la temperatura
                print("No se encontró un sensor válido para la GPU. Reintentando...")
                time.sleep(5)  # Espera 5 segundos antes de reintentar
                continue
            if temp > 60:  # Umbral para GPU
                ip_address = socket.gethostbyname(socket.gethostname())
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                message = (
                    f"{timestamp} + Control de temperatura de la GPU + {ip_address}"
                )

                write_log(message)
                log_to_db(
                    {
                        "timestamp": timestamp,
                        "type": "GPU Temperature",
                        "ip": ip_address,
                        "value": temp,
                    }
                )
                asyncio.run(send_telegram_message(message))
        except Exception as e:
            print(f"Error en monitor_gpu: {e}")
        time.sleep(5)  # Pausa para evitar sobrecargar el sistema


def monitor_memory():
    while True:
        memory = psutil.virtual_memory().percent
        if memory > 80:  # Umbral de memoria
            ip_address = socket.gethostbyname(socket.gethostname())
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"{timestamp} + Utilización de memoria + {ip_address}"

            write_log(message)
            log_to_db(
                {
                    "timestamp": timestamp,
                    "type": "Memory Usage",
                    "ip": ip_address,
                    "value": memory,
                }
            )
            asyncio.run(send_telegram_message(message))


# Crear hilos
cpu_thread = threading.Thread(target=monitor_temperature)
gpu_thread = threading.Thread(target=monitor_gpu)
memory_thread = threading.Thread(target=monitor_memory)

# Iniciar hilos
cpu_thread.start()
gpu_thread.start()
memory_thread.start()

# Asegurarse de que los hilos no se cierren
cpu_thread.join()
gpu_thread.join()
memory_thread.join()
