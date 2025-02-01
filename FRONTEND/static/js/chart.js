let chartPeriod = '6mo';
let chartType = 'candlestick';
let stockChart = null;
let indicators = {
    VOL: true,
    MA: false,
    BB: false,
    RSI: false
};

async function fetchChartData(symbol) {
    if (!symbol || typeof symbol !== 'string') {
        console.error('Invalid symbol:', symbol);
        return null;
    }

    try {
        const token = localStorage.getItem('token');
        const headers = {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };

        const response = await fetch(`/api/stock/${symbol}/chart?period=${chartPeriod}`, {
            method: 'GET',
            headers: headers
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching chart data:', error);
        throw error;
    }
}

async function createStockChart(symbol) {
    if (!symbol || typeof symbol !== 'string') {
        console.error('Invalid symbol:', symbol);
        return;
    }

    try {
        const chartData = await fetchChartData(symbol);
        if (!chartData || !chartData.dates || !chartData.prices) {
            console.error('Invalid chart data received:', chartData);
            return;
        }

        // Get the canvas element
        const chartContainer = document.getElementById('chartContainer');
        if (!chartContainer) {
            console.error('Chart container not found');
            return;
        }

        // Clear existing canvas and create a new one
        chartContainer.innerHTML = '';
        const canvas = document.createElement('canvas');
        canvas.id = 'stockChart';
        chartContainer.appendChild(canvas);

        const ctx = canvas.getContext('2d');
        if (!ctx) {
            console.error('Could not get 2D context');
            return;
        }

        // Destroy existing chart if it exists
        if (stockChart instanceof Chart) {
            stockChart.destroy();
        }

        const chartConfig = {
            type: chartType,
            data: {
                datasets: [{
                    label: symbol,
                    data: chartData.dates.map((date, i) => ({
                        x: new Date(date),
                        o: chartData.opens[i],
                        h: chartData.highs[i],
                        l: chartData.lows[i],
                        c: chartData.prices[i]
                    }))
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: {
                        left: 10,
                        right: 10
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'month',
                            displayFormats: {
                                month: 'MMM yyyy'
                            }
                        },
                        grid: {
                            color: 'rgba(0, 255, 0, 0.1)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#00ff00',
                            font: {
                                family: 'monospace'
                            }
                        }
                    },
                    y: {
                        position: 'left',
                        grid: {
                            color: 'rgba(0, 255, 0, 0.1)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#00ff00',
                            font: {
                                family: 'monospace'
                            }
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: `${symbol} Stock Price`,
                        color: '#00ff00',
                        font: {
                            family: 'monospace',
                            size: 16
                        }
                    },
                    legend: {
                        display: false
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        borderColor: '#00ff00',
                        borderWidth: 1,
                        titleColor: '#00ff00',
                        bodyColor: '#00ff00',
                        titleFont: {
                            family: 'monospace'
                        },
                        bodyFont: {
                            family: 'monospace'
                        },
                        callbacks: {
                            label: function(context) {
                                const point = context.raw;
                                return [
                                    `O: $${point.o.toFixed(2)}`,
                                    `H: $${point.h.toFixed(2)}`,
                                    `L: $${point.l.toFixed(2)}`,
                                    `C: $${point.c.toFixed(2)}`
                                ];
                            }
                        }
                    }
                }
            }
        };

        stockChart = new Chart(ctx, chartConfig);

        // Add chart controls if they don't exist
        if (!document.querySelector('.chart-controls')) {
            const controlsHtml = `
                <div class="chart-controls">
                    <span>Chart Type: </span>
                    <select id="chartTypeSelect" onchange="updateChartType(this.value)">
                        <option value="candlestick" ${chartType === 'candlestick' ? 'selected' : ''}>CANDLESTICK</option>
                        <option value="line" ${chartType === 'line' ? 'selected' : ''}>LINE</option>
                    </select>
                    <span>Period: </span>
                    <select id="periodSelect" onchange="updatePeriod(this.value)">
                        <option value="1mo">1M</option>
                        <option value="3mo">3M</option>
                        <option value="6mo" selected>6M</option>
                        <option value="1y">1Y</option>
                        <option value="2y">2Y</option>
                    </select>
                    <span>Indicators: </span>
                    <label><input type="checkbox" checked onchange="toggleIndicator('VOL', this.checked)"> VOL</label>
                    <label><input type="checkbox" onchange="toggleIndicator('MA', this.checked)"> MA</label>
                    <label><input type="checkbox" onchange="toggleIndicator('BB', this.checked)"> BB</label>
                    <label><input type="checkbox" onchange="toggleIndicator('RSI', this.checked)"> RSI</label>
                </div>
            `;
            chartContainer.insertAdjacentHTML('beforebegin', controlsHtml);
        }

    } catch (error) {
        console.error('Error creating chart:', error);
        showError(`Failed to create chart: ${error.message}`);
    }
}

function updateChartType(type) {
    chartType = type;
    const symbol = document.getElementById('stockSymbol').value;
    if (symbol) createStockChart(symbol);
}

function updatePeriod(period) {
    chartPeriod = period;
    const symbol = document.getElementById('stockSymbol').value;
    if (symbol) createStockChart(symbol);
}

function toggleIndicator(indicator, enabled) {
    indicators[indicator] = enabled;
    const symbol = document.getElementById('stockSymbol').value;
    if (symbol) createStockChart(symbol);
}

function toggleChartType() {
    const btn = document.getElementById('chartTypeToggle');
    if (chartType === 'candlestick') {
        chartType = 'line';
        btn.textContent = 'Switch to Candlestick Chart';
    } else {
        chartType = 'candlestick';
        btn.textContent = 'Switch to Line Chart';
    }
    
    const symbol = document.getElementById('stockSymbol').value;
    if (symbol) {
        createStockChart(symbol);
    }
}

async function updateChart(symbol) {
    if (!symbol || typeof symbol !== 'string') {
        console.error('Invalid symbol:', symbol);
        return;
    }
    try {
        await createStockChart(symbol);
    } catch (error) {
        console.error('Error updating chart:', error);
    }
}

// Make functions available globally
window.createStockChart = createStockChart;
window.updateChart = updateChart;
window.updateChartType = updateChartType;
window.updatePeriod = updatePeriod;
window.toggleIndicator = toggleIndicator;
window.toggleChartType = toggleChartType; 