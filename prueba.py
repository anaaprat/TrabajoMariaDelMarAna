import threading
import time
import os
import json
from datetime import datetime
import subprocess
import asyncio
import psutil
import socket
from pymongo import MongoClient
from telegram import Bot

class Monitor:
    def _init_(self):
        self._umbral_temperatura = 0
        self.log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.log')
        self._mongo_uri = "mongodb://localhost:27017/"
        self._db_name = "TrabajoMariaDelMarAna"
        self._collection_name = "monitoring_db"
        self._max_mongo_entries = 5000
        self._limite_log = 5
        self._telegram_token = '7380846438:AAG3zBi-k7D8CR-jEuuQMguKvGADQDLLLj0'
        self._telegram_chat_id = '7936967176'
        self._lock = threading.Lock()

        self._cpu_temp = None
        self._gpu_temp = None
        self._memory_usage = None
        self._tasks_running = None
        self._ip_address = None

        self._threads = [
    threading.Thread(target=self.monitor_cpu_temp, daemon=True),
    threading.Thread(target=self.monitor_gpu_temp, daemon=True),
    threading.Thread(target=self.monitor_memory_usage, daemon=True),
    threading.Thread(target=self.monitor_tasks_running, daemon=True),
    threading.Thread(target=self.monitor_ip_address, daemon=True),
]
    def run(self):
        for thread in self._threads:
            thread.start()

        while True:
            print(f"CPU Temp: {self._cpu_temp}, GPU Temp: {self._gpu_temp}, "
                  f"Mem Usage: {self._memory_usage}, Tasks: {self._tasks_running}, IP: {self._ip_address}")

            if self._cpu_temp is not None and self._cpu_temp > self._umbral_temperatura:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                data = {
                    "timestamp": timestamp,
                    "cpu_temp": self._cpu_temp,
                    "gpu_temp": self._gpu_temp,
                    "memory_usage": self._memory_usage,
                    "tasks_running": self._tasks_running,
                    "ip_address": self._ip_address,
                }
                self.write_log(data)
                self.save_to_mongo(data)
                self.send_telegram_message(data)
                print(f"[ALERTA] Datos enviados: {data}")
                time.sleep(10)

    def monitor_cpu_temp(self):
        while True:
            time.sleep(5)
            self._cpu_temp = self.get_cpu_temp_from_openhardwaremonitor()
            print(f"[CPU Temp] Temperatura desde OpenHardwareMonitor: {self._cpu_temp}°C")

    def convert_txt_to_json(self, input_file_path , output_file_path):
        try:
            with open(input_file_path, 'r') as file:
                lines = file.readlines()

            data = {}
            stack = []
            current = data

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                if ":" in stripped:
                    key, value = map(str.strip, stripped.split(":", 1))
                    if value.isdigit():
                        value = int(value)
                    elif value.replace('.', '', 1).isdigit():
                        value = float(value)
                    current[key] = value
                elif stripped.startswith("{"):
                    new_section = {}
                    stack.append(current)
                    key = stripped.strip("{}").strip()
                    current[key] = new_section
                    current = new_section
                elif stripped.startswith("}"):
                    current = stack.pop()

            with open(output_file_path, 'w') as json_file:
                json.dump(data, json_file, indent=4)

            print(f"Archivo convertido exitosamente a {output_file_path}")
        except Exception as e:
            print(f"Error al convertir el archivo: {e}")

    def get_cpu_temp_from_openhardwaremonitor(self):
        try:
            json_file_path = "C:\\Users\\Pablo\\Desktop\\cosas clase\\Programas Varios\\Programa datos pc\\OpenHardwareMonitor.Report.json"
            with open(json_file_path, "r") as file:
                data = json.load(file)
                for hardware in data.get("Children", []):
                    if "CPU" in hardware["Text"]:
                        for sensor in hardware.get("Children", []):
                            if "Temperature" in sensor["Text"]:
                                return float(sensor["Value"].split("°")[0])
        except Exception as e:
            print(f"Error leyendo el archivo JSON: {e}")
            return None

    def monitor_gpu_temp(self):
        while True:
            time.sleep(5)
            try:
                output = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                    shell=True
                )
                self._gpu_temp = float(output.decode("utf-8").strip())
            except Exception:
                self._gpu_temp = None

    def monitor_memory_usage(self):
        while True:
            time.sleep(5)
            mem = psutil.virtual_memory()
            self._memory_usage = mem.percent

    def monitor_tasks_running(self):
        while True:
            time.sleep(5)
            self._tasks_running = len(psutil.pids())

    def monitor_ip_address(self):
        while True:
            time.sleep(5)
            hostname = socket.gethostname()
            self._ip_address = socket.gethostbyname(hostname)

    def write_log(self, data):
        with self._lock:
            if not os.path.isfile(self._log_path):
                with open(self._log_path, "w"):
                    pass

            with open(self._log_path, "a+") as log_file:
                log_file.seek(0)
                lines = log_file.readlines()

                if len(lines) >= self._limite_log * 4:
                    lines = lines[4:]

                log_entry = (
                    f"{data['timestamp']} - CPU Temp: {data['cpu_temp']}°C, IP: {data['ip_address']}\n"
                    f"{data['timestamp']} - GPU Temp: {data['gpu_temp']}°C\n"
                    f"Memory Usage: {data['memory_usage']}%, Tasks: {data['tasks_running']}\n"
                )
                lines.append(log_entry)
                log_file.seek(0)
                log_file.truncate()
                log_file.writelines(lines)

    def save_to_mongo(self, data):
        client = MongoClient(self._mongo_uri)
        db = client[self._db_name]
        collection = db[self._collection_name]

        if collection.count_documents({}) >= self._max_mongo_entries:
            oldest_entry = collection.find_one(sort=[("_id", 1)])
            collection.delete_one({"_id": oldest_entry["_id"]})

        collection.insert_one(data)

    def send_telegram_message(self, data):
        message = (
            f"Último registro:\n"
            f"{data['timestamp']} - CPU Temp: {data['cpu_temp']}°C, GPU Temp: {data['gpu_temp']}°C\n"
            f"Memory Usage: {data['memory_usage']}%, Tasks: {data['tasks_running']}\n"
            f"IP: {data['ip_address']}"
        )
        asyncio.run(self._send_telegram_async(message))

    async def _send_telegram_async(self, message):
        bot = Bot(token=self._telegram_token)
        await bot.send_message(chat_id=self._telegram_chat_id, text=message)


if __name__ == "_main_":
    input_txt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "OpenHardwareMonitor.Report.txt")
    output_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "OpenHardwareMonitorReport.json")

    monitor = Monitor()
    monitor.convert_txt_to_json(input_txt_path, output_json_path)
    monitor.run()