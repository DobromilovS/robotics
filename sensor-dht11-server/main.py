from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import serial
import json
import asyncio
import threading
import time
from datetime import datetime
import os
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()

sensor_data = {
    'temperature': [],
    'humidity': [],
    'timestamps': [],
    'current_temp': 0,
    'current_humidity': 0
}

MAX_DATA_POINTS = 50
ser = None
serial_connected = False

SERIAL_PORT = os.getenv('SERIAL_PORT', 'COM3')
BAUD_RATE = int(os.getenv('BAUD_RATE', '9600'))


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: dict):
        disconnected_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected_connections.append(connection)
        for connection in disconnected_connections:
            self.disconnect(connection)


manager = ConnectionManager()


def init_serial():
    global ser, serial_connected
    try:
        available_ports = [port.device for port in serial.tools.list_ports.comports()]
        print(f"Available serial ports: {available_ports}")

        if SERIAL_PORT not in available_ports:
            print(f"Serial port {SERIAL_PORT} not found!")
            return False

        if ser and ser.is_open:
            ser.close()
            time.sleep(1)

        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        serial_connected = True
        print(f"Connected to Arduino on {SERIAL_PORT}")

        ser.reset_input_buffer()
        time.sleep(2)
        return True
    except Exception as e:
        print(f"Serial connection error: {e}")
        serial_connected = False
        return False


def close_serial():
    global ser, serial_connected
    if ser and ser.is_open:
        ser.close()
        print("Serial port closed")
    serial_connected = False


def process_sensor_data(json_string: str):
    try:
        if not json_string.startswith('{'):
            print(f"Skipping non-JSON: {json_string}")
            return

        data = json.loads(json_string)
        temp = float(data.get('temperature', 0))
        hum = float(data.get('humidity', 0))

        if temp < -40 or temp > 80 or hum < 0 or hum > 100:
            print(f"Invalid sensor values: Temp={temp}, Hum={hum}")
            return

        sensor_data['current_temp'] = temp
        sensor_data['current_humidity'] = hum
        timestamp = datetime.now().strftime("%H:%M:%S")

        sensor_data['temperature'].append(temp)
        sensor_data['humidity'].append(hum)
        sensor_data['timestamps'].append(timestamp)

        if len(sensor_data['temperature']) > MAX_DATA_POINTS:
            sensor_data['temperature'].pop(0)
            sensor_data['humidity'].pop(0)
            sensor_data['timestamps'].pop(0)

        message = {
            'temperature': temp,
            'humidity': hum,
            'timestamp': timestamp,
            'history': {
                'temperatures': sensor_data['temperature'][-10:],
                'humidities': sensor_data['humidity'][-10:],
                'timestamps': sensor_data['timestamps'][-10:]
            }
        }

        asyncio.run_coroutine_threadsafe(
            manager.broadcast(message),
            asyncio.get_event_loop()
        )
        print(f"Data sent: Temp={temp:.1f}C, Hum={hum:.1f}%")

    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}, data: {json_string}")
    except Exception as e:
        print(f"Processing error: {e}")


def read_serial_data():
    global serial_connected
    while True:
        try:
            if serial_connected and ser and ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                if line:
                    print(f"Raw data: {line}")
                    process_sensor_data(line)
            elif not serial_connected:
                if init_serial():
                    print("Reconnected to Arduino")
        except Exception as e:
            print(f"Error in read_serial_data: {e}")
            serial_connected = False
        time.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting DHT11 Monitor Server...")
    try:
        import serial.tools.list_ports
    except ImportError:
        print("serial.tools not available")

    if init_serial():
        thread = threading.Thread(target=read_serial_data)
        thread.daemon = True
        thread.start()
        print("Serial reader thread started")
    else:
        print("Running without serial connection")

    yield

    print("Shutting down server...")
    close_serial()
    print("Server shutdown complete")


app = FastAPI(
    title="DHT11 Sensor Monitor",
    description="Real-time temperature and humidity monitoring with Arduino",
    version="1.0.0",
    lifespan=lifespan
)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/temperature", response_class=HTMLResponse)
async def read_temperature(request: Request):
    return templates.TemplateResponse("temp.html", {"request": request})


@app.get("/humidity", response_class=HTMLResponse)
async def read_humidity(request: Request):
    return templates.TemplateResponse("hum.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({
            'temperature': sensor_data['current_temp'],
            'humidity': sensor_data['current_humidity'],
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'history': {
                'temperatures': sensor_data['temperature'][-10:],
                'humidities': sensor_data['humidity'][-10:],
                'timestamps': sensor_data['timestamps'][-10:]
            }
        })

        while True:
            data = await websocket.receive_text()
            print(f"Message from client: {data}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")


@app.get("/api/data")
async def get_current_data():
    return {
        'temperature': sensor_data['current_temp'],
        'humidity': sensor_data['current_humidity'],
        'timestamp': datetime.now().strftime("%H:%M:%S")
    }


@app.get("/api/history")
async def get_history_data():
    return {
        'temperatures': sensor_data['temperature'],
        'humidities': sensor_data['humidity'],
        'timestamps': sensor_data['timestamps']
    }


@app.get("/api/health")
async def health_check():
    return {
        'status': 'healthy',
        'serial_connected': serial_connected,
        'websocket_clients': len(manager.active_connections),
        'data_points': len(sensor_data['temperature'])
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=5000,
        reload=True,
        log_level="info"
    )