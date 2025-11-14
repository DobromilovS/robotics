const currentTemp = document.getElementById('currentTemp');
const currentHum = document.getElementById('currentHum');
const tempTime = document.getElementById('tempTime');
const humTime = document.getElementById('humTime');
const connectionStatus = document.getElementById('connectionStatus');

const socket = io();

socket.on('connect', function() {
    connectionStatus.textContent = '✅ Connected to server';
    connectionStatus.className = 'status connected';
});

socket.on('sensor_update', function(data) {
    currentTemp.textContent = `${data.temperature.toFixed(1)} °C`;
    currentHum.textContent = `${data.humidity.toFixed(1)} %`;
    tempTime.textContent = data.timestamp;
    humTime.textContent = data.timestamp;
    connectionStatus.textContent = '✅ Connected - Live Data';
    connectionStatus.className = 'status connected';
});

socket.on('disconnect', function() {
    connectionStatus.textContent = '❌ Disconnected from server';
    connectionStatus.className = 'status disconnected';
});

socket.on('connect_error', function(error) {
    connectionStatus.textContent = '❌ Connection error';
    connectionStatus.className = 'status disconnected';
});