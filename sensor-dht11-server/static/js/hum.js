const currentHum = document.getElementById('currentHum');
const humTime = document.getElementById('humTime');
const connectionStatus = document.getElementById('connectionStatus');

const socket = io();

socket.on('connect', function() {
    connectionStatus.textContent = '✅ Connected to server';
    connectionStatus.className = 'connection-status connected';
    console.log('Socket.IO connected');
});

socket.on('sensor_update', function(data) {
    console.log('Data received:', data);
    updateDisplay(data);
});

socket.on('disconnect', function() {
    connectionStatus.textContent = '❌ Disconnected';
    connectionStatus.className = 'connection-status';
    console.log('Socket.IO disconnected');
});

const humChart = new Chart(document.getElementById('humChart'), {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Humidity %',
            data: [],
            borderColor: '#4ecdc4',
            backgroundColor: 'rgba(78, 205, 196, 0.1)',
            borderWidth: 3,
            tension: 0.4,
            fill: true,
            pointBackgroundColor: '#4ecdc4',
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
                    text: '%',
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

function updateDisplay(data) {
    currentHum.textContent = `${data.humidity.toFixed(1)} %`;
    humTime.textContent = data.timestamp;
    updateChart(data.history);
    connectionStatus.textContent = '✅ Connected - Live Data';
    connectionStatus.className = 'connection-status connected';
}

function updateChart(history) {
    if (history && history.humidities && history.timestamps) {
        humChart.data.labels = history.timestamps;
        humChart.data.datasets[0].data = history.humidities;
        humChart.update('none');
    }
}