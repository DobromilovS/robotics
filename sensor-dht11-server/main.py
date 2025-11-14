from flask import Flask, render_template, request
from flask_socketio import SocketIO
from dotenv import load_dotenv
import serial
import json
import threading
import time
from datetime import datetime
import atexit
import os

app = Flask(__name__)
load_dotenv()

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
socketio = SocketIO(app, cors_allowed_origins="*")

SERIAL_PORT = os.getenv('SERIAL_PORT')
BAUD_RATE = os.getenv('BAUD_RATE')

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


def init_serial():
    global ser, serial_connected
    try:
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


def process_sensor_data(json_string):
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

        socketio.emit('sensor_update', {
            'temperature': temp,
            'humidity': hum,
            'timestamp': timestamp,
            'history': {
                'temperatures': sensor_data['temperature'][-10:],
                'humidities': sensor_data['humidity'][-10:],
                'timestamps': sensor_data['timestamps'][-10:]
            }
        })
        # print(f"Data sent: Temp={temp:.1f}°C, Hum={hum:.1f}%") для проверки приема использовал

    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}, data: {json_string}")
    except Exception as e:
        print(f"Processing error: {e}")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/temperature')
def temperature():
    return render_template('temp.html')


@app.route('/humidity')
def humidity():
    return render_template('hum.html')


@socketio.on('connect')
def handle_connect():
    print("Client connected")
    socketio.emit('sensor_update', {
        'temperature': sensor_data['current_temp'],
        'humidity': sensor_data['current_humidity'],
        'timestamp': datetime.now().strftime("%H:%M:%S"),
        'history': {
            'temperatures': sensor_data['temperature'][-10:],
            'humidities': sensor_data['humidity'][-10:],
            'timestamps': sensor_data['timestamps'][-10:]
        }
    })


@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

atexit.register(close_serial)

if __name__ == '__main__':
    if init_serial():
        thread = threading.Thread(target=read_serial_data)
        thread.daemon = True
        thread.start()
    socketio.run(app, host='127.0.0.1', port=5000, debug=False, allow_unsafe_werkzeug=True)