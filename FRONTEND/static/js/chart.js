let chartPeriod = '6M';
let chartType = 'candlestick';
let stockChart = null;
let indicators = {
    VOL: false,
    MA: false,
    BB: false,
    RSI: false
};
let currentChart = null;

const INDICATOR_CONFIGS = {
    VOL: {
        name: 'Volume',
        description: 'Trading volume represented as bars',
        color: 'rgba(0, 255, 0, 0.3)',
        order: 2
    },
    MA: {
        name: 'Moving Average (20)',
        description: '20-day simple moving average',
        color: '#ffff00',
        order: 1
    },
    BB: {
        name: 'Bollinger Bands',
        description: '20-day moving average with 2 standard deviations',
        upperColor: 'rgba(0, 255, 0, 0.5)',
        lowerColor: 'rgba(255, 0, 0, 0.5)',
        order: 1
    },
    RSI: {
        name: 'RSI (14)',
        description: '14-day relative strength index',
        color: '#00ffff',
        order: 3
    }
};

const TIME_UNITS = {
    '1M': { unit: 'day', displayFormats: { day: 'MMM d' } },
    '3M': { unit: 'month', displayFormats: { month: 'MMM' } },
    '6M': { unit: 'month', displayFormats: { month: 'MMM' } },
    '1Y': { unit: 'month', displayFormats: { month: 'MMM yyyy' } }
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

        const periodMap = {
            '1M': '1mo',
            '3M': '3mo',
            '6M': '6mo',
            '1Y': '1y'
        };
        const apiPeriod = periodMap[chartPeriod] || '6mo';

        const response = await fetch(`/api/stock/${symbol}/chart?period=${apiPeriod}`, {
            method: 'GET',
            headers: headers
        });

        if (!response.ok) {
            console.error(`HTTP error! status: ${response.status}`);
            if (response.status === 404) {
                throw new Error(`No data found for ${symbol}`);
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        // Validate data
        if (!data || !data.dates || !data.prices || !data.opens || 
            !data.highs || !data.lows || !data.volumes ||
            data.dates.length === 0 || data.prices.length === 0) {
            console.error('Invalid data structure:', data);
            throw new Error('Invalid data received from server');
        }
        
        // Ensure all arrays are the same length
        const length = data.dates.length;
        if ([data.opens, data.highs, data.lows, data.prices, data.volumes]
            .some(arr => arr.length !== length)) {
            console.error('Array length mismatch:', {
                dates: data.dates.length,
                opens: data.opens.length,
                highs: data.highs.length,
                lows: data.lows.length,
                prices: data.prices.length,
                volumes: data.volumes.length
            });
            throw new Error('Data arrays have mismatched lengths');
        }
        
        // Log successful data validation
        console.log('Chart data validated successfully:', {
            dataPoints: length,
            firstDate: data.dates[0],
            lastDate: data.dates[length - 1]
        });
        
        return data;
    } catch (error) {
        console.error('Error fetching chart data:', error);
        throw error;
    }
}

async function createStockChart(symbol) {
    console.log('Creating chart for symbol:', symbol);
    if (!symbol) {
        console.log('No symbol provided for chart creation');
        return;
    }

    if (typeof symbol !== 'string') {
        console.error('Invalid symbol type:', typeof symbol);
        return;
    }

    try {
        const chartData = await fetchChartData(symbol);
        console.log('Chart data received:', chartData);
        if (!chartData || !chartData.dates || !chartData.prices) {
            console.error('Invalid chart data received:', chartData);
            return;
        }

        // Process data for indicators
        const processedData = processChartData(chartData);
        
        // Clear any existing chart
        if (currentChart) {
            currentChart.destroy();
            currentChart = null;
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

        // Configure chart based on type
        const config = {
            type: chartType === 'candlestick' ? 'candlestick' : 'line',
            data: {
                datasets: [{
                    label: symbol,
                    data: chartType === 'candlestick' ? processedData.candlestick : processedData.line,
                    type: chartType === 'candlestick' ? 'candlestick' : 'line',
                    parsing: false,  // Disable parsing to use raw data
                    borderColor: '#00ff00',
                    color: '#00ff00',
                    candlestick: {
                        color: {
                            up: '#00ff00',
                            down: '#ff0000',
                        },
                        border: {
                            up: '#00ff00',
                            down: '#ff0000',
                        },
                        wick: {
                            color: {
                                up: '#00ff00',
                                down: '#ff0000'
                            }
                        }
                    },
                    backgroundColor: function(context) {
                        if (chartType === 'line') return 'transparent';
                        if (chartType === 'area') {
                            const ctx = context.chart.ctx;
                            const gradient = ctx.createLinearGradient(0, 0, 0, context.chart.height);
                            gradient.addColorStop(0, 'rgba(0, 255, 0, 0.3)');
                            gradient.addColorStop(1, 'rgba(0, 255, 0, 0)');
                            return gradient;
                        }
                        // For candlestick
                        const value = context.raw;
                        if (!value || typeof value.o === 'undefined' || typeof value.c === 'undefined') {
                            return 'rgba(0, 255, 0, 0.5)';
                        }
                        return value.o > value.c 
                            ? 'rgba(255, 0, 0, 1)'  // Red for bearish
                            : 'rgba(0, 255, 0, 1)'; // Green for bullish
                    },
                    borderWidth: chartType === 'area' ? 1 : 2,
                    tension: 0.1,
                    fill: chartType === 'area' ? {
                        target: 'origin',
                        above: 'rgba(0, 255, 0, 0.1)'
                    } : false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                animation: false,  // Disable animations for better performance
                elements: {
                    candlestick: {
                        width: 8,  // Make candlesticks wider
                        capWidth: 4,  // Width of the cap lines
                        wickWidth: 2  // Width of the wick lines
                    }
                },
                hover: {
                    mode: 'nearest',
                    intersect: false
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: TIME_UNITS[chartPeriod].unit,
                            displayFormats: TIME_UNITS[chartPeriod].displayFormats,
                            parser: 'x'  // Use the timestamp directly
                        },
                        ticks: {
                            color: '#00ff00'
                        },
                        grid: {
                            color: '#004400'
                        }
                    },
                    y: {
                        position: 'right',
                        ticks: {
                            color: '#00ff00',
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        },
                        grid: {
                            color: '#004400'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const point = context.raw;
                                if (chartType === 'candlestick' && point && point.o) {
                                    return [
                                        `O: $${point.o.toFixed(2)}`,
                                        `H: $${point.h.toFixed(2)}`,
                                        `L: $${point.l.toFixed(2)}`,
                                        `C: $${point.c.toFixed(2)}`
                                    ];
                                }
                                return `Price: $${(point.c || point.y || 0).toFixed(2)}`;
                            }
                        }
                    }
                }
            }
        };

        // Create new chart with base configuration
        currentChart = new Chart(ctx, config);

        // Add enabled indicators with processed data
        if (processedData && processedData.ohlc && processedData.ohlc.length) {
            Object.entries(indicators).forEach(([indicator, enabled]) => {
                if (enabled) {
                    addIndicator(indicator, processedData.ohlc);
                }
            });
        }

    } catch (error) {
        console.error('Error creating chart:', error);
        showError(`Failed to create chart: ${error.message}`);
    }
}

function updateChartType(type) {
    if (!currentChart || !currentChart.data || !currentChart.data.datasets) {
        console.error('No chart data available');
        return;
    }

    chartType = type;
    const symbol = document.getElementById('ticker').value;
    
    try {
        // Recreate the chart with the new type
        createStockChart(symbol);
    } catch (error) {
        console.error('Error updating chart type:', error);
    }
}

function updatePeriod(period) {
    if (!period || period === chartPeriod) return;

    // Validate period
    const validPeriods = ['1M', '3M', '6M', '1Y'];
    if (!validPeriods.includes(period)) {
        console.error('Invalid period:', period);
        return;
    }

    chartPeriod = period;
    const symbol = document.getElementById('ticker').value;
    if (symbol) {
        createStockChart(symbol);
    }
}

function toggleIndicator(indicator) {
    try {
        if (!currentChart || !currentChart.data || !currentChart.data.datasets) {
            console.error('No chart data available');
            return;
        }

        indicators[indicator] = !indicators[indicator];
        const data = currentChart.data.datasets[0].data;
        if (!data || !data.length) {
            console.error('No data points available');
            return;
        }

        // Remove existing indicator if it exists
        currentChart.data.datasets = currentChart.data.datasets.filter(
            dataset => !dataset.label.includes(indicator)
        );

        if (indicators[indicator]) {
            // Get the correct data format based on chart type
            const indicatorData = data.map(d => ({
                x: d.x,
                o: chartType === 'candlestick' ? d.o : d.y,
                h: chartType === 'candlestick' ? d.h : d.y,
                l: chartType === 'candlestick' ? d.l : d.y,
                c: chartType === 'candlestick' ? d.c : d.y,
                y: chartType === 'candlestick' ? d.c : d.y,
                volume: d.volume || 0
            }));
            
            try {
                addIndicator(indicator, indicatorData);
            } catch (error) {
                console.error(`Error adding ${indicator}:`, error);
                indicators[indicator] = false;  // Reset indicator state on error
                const checkbox = document.getElementById(indicator.toLowerCase());
                if (checkbox) checkbox.checked = false;
            }
        }

        currentChart.update('none');  // Disable animation for smoother updates
    } catch (error) {
        console.error('Error toggling indicator:', error);
    }
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
    
    const symbol = document.getElementById('ticker').value;
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

// Update event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Chart type change
    const chartTypeSelect = document.getElementById('chartType');
    if (chartTypeSelect) {
        chartTypeSelect.addEventListener('change', function() {
            updateChartType(this.value);
        });
    }

    // Period change
    const periodSelect = document.getElementById('period');
    if (periodSelect) {
        periodSelect.addEventListener('change', function() {
            updatePeriod(this.value);
        });
    }

    // Indicator toggles
    ['vol', 'ma', 'bb', 'rsi'].forEach(indicator => {
        const checkbox = document.getElementById(indicator.toLowerCase());
        if (checkbox) {
            // Force initial state to match indicators object
            checkbox.checked = false;
            indicators[indicator.toUpperCase()] = false;
            checkbox.addEventListener('change', function() {
                toggleIndicator(indicator.toUpperCase());
            });
        }
    });
});

// Update chart configuration
const defaultChartConfig = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
        duration: 0  // Disable animations for better performance
    },
    layout: {
        padding: {
            left: 10,
            right: 10
        }
    }
};

function addIndicator(indicator, data) {
    if (!currentChart) {
        console.error('No chart available');
        return;
    }

    try {
        // Remove existing indicator if it exists
        currentChart.data.datasets = currentChart.data.datasets.filter(
            dataset => !dataset.label.includes(indicator)
        );

        // Ensure data is valid
        if (!data || !data.length) {
            throw new Error('No valid data for indicator');
        }

        switch(indicator) {
            case 'VOL':
                const volumeData = {
                    label: 'Volume',
                    data: data.map(d => ({
                        x: d.x,
                        y: d.volume
                    })),
                    type: 'bar',
                    backgroundColor: 'rgba(0, 255, 0, 0.3)',
                    borderColor: '#00ff00',
                    yAxisID: 'volume',
                    order: 2,
                    barThickness: 3
                };
                currentChart.data.datasets.push(volumeData);

                // Add volume scale if it doesn't exist
                if (!currentChart.options.scales.volume) {
                    currentChart.options.scales.volume = {
                        position: 'right',
                        grid: {
                            drawOnChartArea: false,
                            color: '#004400'
                        },
                        ticks: {
                            color: '#00ff00',
                            callback: function(value) {
                                return value >= 1e6 
                                    ? (value / 1e6).toFixed(1) + 'M'
                                    : value.toLocaleString();
                            }
                        }
                    };
                }
                break;

            case 'MA':
                const maData = calculateMA(data, 20);
                currentChart.data.datasets.push({
                    label: 'MA(20)',
                    data: maData,
                    type: 'line',
                    borderColor: '#ffff00',
                    borderWidth: 1,
                    fill: false,
                    order: 1
                });
                break;

            case 'BB':
                const { upper, middle, lower } = calculateBollingerBands(data, 20, 2);
                // Add middle band (SMA)
                currentChart.data.datasets.push({
                    label: 'BB Middle',
                    data: middle,
                    borderColor: INDICATOR_CONFIGS.BB.color,
                    borderWidth: 1,
                    fill: false,
                    order: 1
                });
                // Add upper band
                currentChart.data.datasets.push({
                    label: 'BB Upper',
                    data: upper,
                    borderColor: INDICATOR_CONFIGS.BB.upperColor,
                    borderWidth: 1,
                    fill: false,
                    order: 1
                });
                // Add lower band
                currentChart.data.datasets.push({
                    label: 'BB Lower',
                    data: lower,
                    borderColor: INDICATOR_CONFIGS.BB.lowerColor,
                    borderWidth: 1,
                    fill: false,
                    order: 1
                });
                break;

            case 'RSI':
                const rsiData = calculateRSI(data, 14);
                currentChart.data.datasets.push({
                    label: 'RSI',
                    data: rsiData,
                    borderColor: INDICATOR_CONFIGS.RSI.color,
                    borderWidth: 1,
                    fill: false,
                    yAxisID: 'rsi'
                });
                
                // Add RSI scale
                currentChart.options.scales.rsi = {
                    position: 'right',
                    min: 0,
                    max: 100,
                    grid: {
                        drawOnChartArea: false,
                        color: '#004400'
                    },
                    ticks: {
                        color: '#00ff00'
                    }
                };
                break;
        }

        currentChart.update('none');
    } catch (error) {
        console.error('Error adding indicator:', error, indicator);
        throw error;  // Rethrow to handle in toggleIndicator
    }
}

function calculateMA(data, period) {
    const prices = data.map(d => chartType === 'candlestick' ? d.c : d.y);
    const ma = [];
    const dates = data.map(d => d.x);  // Already in milliseconds
    
    for (let i = 0; i < prices.length; i++) {
        if (i < period - 1) {
            ma.push(null);
            continue;
        }
        const sum = prices.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
        ma.push(sum / period);
    }
    
    return ma.map((value, i) => ({
        x: dates[i],
        y: value
    }));
}

function calculateBollingerBands(data, period = 20, stdDev = 2) {
    const prices = data.map(d => d.c);
    const middle = [];
    const upper = [];
    const lower = [];

    for (let i = 0; i < prices.length; i++) {
        if (i < period - 1) {
            middle.push(null);
            upper.push(null);
            lower.push(null);
            continue;
        }

        const slice = prices.slice(i - period + 1, i + 1);
        const avg = slice.reduce((a, b) => a + b, 0) / period;
        const std = Math.sqrt(
            slice.reduce((a, b) => a + Math.pow(b - avg, 2), 0) / period
        );

        middle.push({ x: data[i].x, y: avg });
        upper.push({ x: data[i].x, y: avg + stdDev * std });
        lower.push({ x: data[i].x, y: avg - stdDev * std });
    }

    return { upper, middle, lower };
}

function calculateRSI(data, period = 14) {
    const prices = data.map(d => d.c);
    const rsi = [];
    let gains = [];
    let losses = [];

    // Calculate initial gains and losses
    for (let i = 1; i < prices.length; i++) {
        const difference = prices[i] - prices[i - 1];
        gains.push(Math.max(difference, 0));
        losses.push(Math.abs(Math.min(difference, 0)));
    }

    // Calculate RSI
    for (let i = 0; i < prices.length; i++) {
        if (i < period) {
            rsi.push(null);
            continue;
        }

        const avgGain = gains.slice(i - period, i).reduce((a, b) => a + b) / period;
        const avgLoss = losses.slice(i - period, i).reduce((a, b) => a + b) / period;
        
        const rs = avgGain / avgLoss;
        const rsiValue = 100 - (100 / (1 + rs));

        rsi.push({
            x: data[i].x,
            y: rsiValue
        });
    }

    return rsi;
}

function processChartData(chartData) {
    // Filter out any invalid data points
    const validData = chartData.dates.map((date, i) => ({
        date: luxon.DateTime.fromISO(date).toMillis(),  // Convert to milliseconds
        o: Number(chartData.opens[i]),
        h: Number(chartData.highs[i]),
        l: Number(chartData.lows[i]),
        c: Number(chartData.prices[i]),
        v: chartData.volumes[i]
    })).filter(d => (
        d.o !== null && d.h !== null && d.l !== null && 
        d.c !== null && d.v !== null && 
        !isNaN(d.o) && !isNaN(d.h) && !isNaN(d.l) && !isNaN(d.c) &&
        typeof d.date === 'number' && !isNaN(d.date)
    ));

    // Create separate datasets for candlestick and line
    const candlestickData = validData.map(d => ({
        x: d.date,
        o: Number(d.o),
        h: Number(d.h),
        l: Number(d.l),
        c: Number(d.c),
        volume: d.v
    }));

    const lineData = validData.map(d => ({
        x: d.date,
        y: Number(d.c),
        volume: d.v
    }));

    return {
        candlestick: candlestickData,
        line: lineData
    };
}

// Make functions available globally
window.createStockChart = createStockChart;
window.updateChart = updateChart;
window.updateChartType = updateChartType;
window.updatePeriod = updatePeriod;
window.toggleIndicator = toggleIndicator;
window.toggleChartType = toggleChartType; 