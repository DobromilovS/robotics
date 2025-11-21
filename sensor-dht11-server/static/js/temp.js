const currentTemp = document.getElementById('currentTemp');
const tempTime = document.getElementById('tempTime');
const connectionStatus = document.getElementById('connectionStatus');

let socket = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

const tempChart = new Chart(document.getElementById('tempChart'), {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Temperature °C',
            data: [],
            borderColor: '#ff6b6b',
            backgroundColor: 'rgba(255, 107, 107, 0.1)',
            borderWidth: 3,
            tension: 0.4,
            fill: true,
            pointBackgroundColor: '#ff6b6b',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: { mode: 'index', intersect: false }
        },
        scales: {
            y: {
                grid: { color: 'rgba(0,0,0,0.1)' },
                ticks: { color: '#666', font: { size: 12 } },
                title: {
                    display: true,
                    text: '°C',
                    color: '#666',
                    font: { size: 12, weight: 'bold' }
                }
            },
            x: {
                grid: { display: false },
                ticks: {
                    color: '#666',
                    font: { size: 11 },
                    maxTicksLimit: 8
                }
            }
        },
        interaction: { intersect: false, mode: 'nearest' },
        animation: { duration: 0 }
    }
});

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    socket = new WebSocket(wsUrl);

    socket.onopen = function(event) {
        console.log('✅ WebSocket connected');
        connectionStatus.textContent = '✅ Connected to server';
        connectionStatus.className = 'connection-status connected';
        reconnectAttempts = 0;
    };

    socket.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('Data received:', data);
            updateDisplay(data);
        } catch (error) {
            console.error('Error parsing message:', error);
        }
    };

    socket.onclose = function(event) {
        console.log('WebSocket disconnected:', event.code, event.reason);

        if (event.code !== 1000) {
            handleDisconnection();
        }
    };

    socket.onerror = function(error) {
        console.error('WebSocket error:', error);
        connectionStatus.textContent = '❌ WebSocket error';
        connectionStatus.className = 'connection-status';
    };
}

function updateDisplay(data) {
    currentTemp.textContent = `${data.temperature.toFixed(1)} °C`;
    tempTime.textContent = data.timestamp;
    updateChart(data.history);
    connectionStatus.textContent = '✅ Connected - Live Data';
    connectionStatus.className = 'connection-status connected';
}

function updateChart(history) {
    if (history && history.temperatures && history.timestamps) {
        tempChart.data.labels = history.timestamps;
        tempChart.data.datasets[0].data = history.temperatures;
        tempChart.update('none');
    }
}

function handleDisconnection() {
    connectionStatus.textContent = '❌ Disconnected - Attempting to reconnect...';
    connectionStatus.className = 'connection-status';

    if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        setTimeout(() => {
            console.log(`Attempting to reconnect... (${reconnectAttempts}/${maxReconnectAttempts})`);
            connectWebSocket();
        }, 3000);
    } else {
        connectionStatus.textContent = '❌ Failed to reconnect. Please refresh the page.';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    connectWebSocket();
    window.addEventListener('beforeunload', function() {
        if (socket) {
            socket.close(1000, 'Page navigation');
        }
    });
});