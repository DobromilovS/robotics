from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from contextlib import asynccontextmanager
import json
import uvicorn
import threading
import serial
import asyncio
import time
from datetime import datetime
import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

current_expression = "neutral"

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

SERIAL_PORT = os.getenv('SERIAL_PORT', 'COM6')
BAUD_RATE = int(os.getenv('BAUD_RATE', '115200'))

class FaceConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        await self.send_current_expression(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_current_expression(self, websocket: WebSocket):
        await websocket.send_text(json.dumps({
            "type": "face_expression",
            "expression": current_expression
        }))

    async def broadcast(self, message: str):
        disconnected_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected_connections.append(connection)
        for connection in disconnected_connections:
            self.disconnect(connection)


class SensorConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        await self.send_current_data(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_current_data(self, websocket: WebSocket):
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

    async def broadcast(self, message: dict):
        disconnected_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected_connections.append(connection)
        for connection in disconnected_connections:
            self.disconnect(connection)


face_manager = FaceConnectionManager()
sensor_manager = SensorConnectionManager()
templates = Jinja2Templates(directory="templates")


def init_serial():
    global ser, serial_connected
    try:
        try:
            import serial.tools.list_ports
            available_ports = [port.device for port in serial.tools.list_ports.comports()]
            print(f"Available serial ports: {available_ports}")

            if SERIAL_PORT not in available_ports:
                print(f"Serial port {SERIAL_PORT} not found! Available: {available_ports}")
                return False
        except ImportError:
            print("serial.tools.list_ports not available, skipping port verification")

        if ser and ser.is_open:
            ser.close()
            time.sleep(1)

        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        serial_connected = True
        print(f"Connected to Arduino on {SERIAL_PORT} at {BAUD_RATE} baud")

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
            sensor_manager.broadcast(message),
            asyncio.get_event_loop()
        )
        print(f"Data sent: Temp={temp:.1f}C, Hum={hum:.1f}%")

    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}, data: {json_string}")
    except Exception as e:
        print(f"Processing error: {e}")


def read_serial_data():
    global serial_connected
    buffer = ""
    while True:
        try:
            if serial_connected and ser and ser.in_waiting > 0:
                data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                buffer += data

                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        print(f"Raw data: {line}")
                        process_sensor_data(line)
            elif not serial_connected:
                if init_serial():
                    print("Reconnected to Arduino")
        except Exception as e:
            print(f"Error in read_serial_data: {e}")
            serial_connected = False
        time.sleep(0.1)

def start_voice_processor():
    try:
        from audio import VoiceProcessor
        voice_processor = VoiceProcessor()
        voice_processor.listen()
    except Exception as e:
        print(f"Error starting voice processor: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting combined server...")
    print(f"Using serial port: {SERIAL_PORT}, baud rate: {BAUD_RATE}")

    if init_serial():
        sensor_thread = threading.Thread(target=read_serial_data)
        sensor_thread.daemon = True
        sensor_thread.start()
        print("Serial reader thread started")
    else:
        print("Running without serial connection")

    try:
        voice_thread = threading.Thread(target=start_voice_processor)
        voice_thread.daemon = True
        voice_thread.start()
        print("Voice processor thread started")
    except Exception as e:
        print(f"Failed to start voice processor: {e}")

    yield

    print("Shutting down server...")
    close_serial()
    print("Server shutdown complete")


app = FastAPI(
    title="Combined Face & Sensor Server",
    description="Face expression control and real-time sensor monitoring",
    version="1.0.0",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_index():
    return FileResponse("templates/face.html")


@app.get("/casino")
async def read_casino():
    return FileResponse("templates/casino.html")


@app.websocket("/ws_face")
async def face_websocket_endpoint(websocket: WebSocket):
    await face_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        face_manager.disconnect(websocket)


class FaceExpression(BaseModel):
    expression: str


@app.post("/change-expression")
async def change_expression(data: FaceExpression):
    global current_expression
    current_expression = data.expression
    await face_manager.broadcast(json.dumps({
        "type": "face_expression",
        "expression": current_expression
    }))
    return {"status": "success"}


@app.post("/casino/spin")
async def casino_spin():
    await face_manager.broadcast(json.dumps({"type": "casino_spin"}))
    return {"status": "success"}


@app.get("/temperature")
async def read_temperature(request: Request):
    return templates.TemplateResponse("temp.html", {"request": request})


@app.get("/humidity")
async def read_humidity(request: Request):
    return templates.TemplateResponse("hum.html", {"request": request})


@app.websocket("/ws_sensors")
async def sensor_websocket_endpoint(websocket: WebSocket):
    await sensor_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Message from sensor client: {data}")
    except WebSocketDisconnect:
        sensor_manager.disconnect(websocket)
        print("Sensor client disconnected")


@app.get("/api/sensor_data")
async def get_current_data():
    return {
        'temperature': sensor_data['current_temp'],
        'humidity': sensor_data['current_humidity'],
        'timestamp': datetime.now().strftime("%H:%M:%S")
    }


@app.get("/api/sensor_history")
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
        'face_websocket_clients': len(face_manager.active_connections),
        'sensor_websocket_clients': len(sensor_manager.active_connections),
        'data_points': len(sensor_data['temperature']),
        'serial_port': SERIAL_PORT,
        'baud_rate': BAUD_RATE
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)