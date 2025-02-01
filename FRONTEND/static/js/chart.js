// Chart functionality
async function createStockChart(symbol, period = '6mo') {
    if (!symbol || !checkAuthStatus()) {
        console.log('Chart creation cancelled: missing symbol or auth');
        return;
    }

    try {
        console.log('Creating chart for:', symbol);
        
        const url = `/api/stock/${symbol}/chart?period=${period}`;
        console.log('Fetching chart data from:', url);

        const headers = {
            'Authorization': `Bearer ${getToken()}`,
            'Content-Type': 'application/json',
            'Accept': 'application/json'  // Add explicit Accept header
        };
        console.log('Request headers:', headers);

        const response = await fetch(url, { headers });

        // Log the response status and headers
        console.log('Response status:', response.status);
        console.log('Response headers:', Object.fromEntries(response.headers.entries()));

        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error(`Expected JSON response but got ${contentType}`);
        }

        const data = await response.json();
        console.log('Chart data:', data);

        // Validate data structure
        if (!data || typeof data !== 'object') {
            throw new Error('Invalid data structure received');
        }

        // Check for error response
        if (data.detail) {
            throw new Error(`Server error: ${data.detail}`);
        }

        // Ensure we have the required data arrays
        const requiredArrays = ['dates', 'opens', 'highs', 'lows', 'closes'];
        for (const key of requiredArrays) {
            if (!Array.isArray(data[key])) {
                console.error(`Missing or invalid ${key} array:`, data[key]);
                throw new Error(`Missing required data array: ${key}`);
            }
        }

        // Create candlestick trace
        const candlestick = {
            x: data.dates,
            open: data.opens,
            high: data.highs,
            low: data.lows,
            close: data.closes,
            type: 'candlestick',
            name: symbol,
            increasing: {line: {color: '#00FF00'}},
            decreasing: {line: {color: '#FF0000'}}
        };

        const traces = [candlestick];

        // Create the layout
        const layout = {
            title: {
                text: `${symbol} Stock Price`,
                font: {
                    color: '#00ff00',
                    size: 16
                }
            },
            paper_bgcolor: '#000000',
            plot_bgcolor: '#000000',
            font: {
                color: '#00ff00',
                family: 'monospace'
            },
            xaxis: {
                title: 'Date',
                gridcolor: '#003300',
                color: '#00ff00',
                rangeslider: {
                    visible: false
                }
            },
            yaxis: {
                title: 'Price',
                gridcolor: '#003300',
                color: '#00ff00',
                side: 'left'
            },
            margin: { t: 30, b: 40, l: 60, r: 50 },
            showlegend: false
        };

        const config = {
            displayModeBar: false,
            responsive: true
        };

        const chartDiv = document.getElementById('stockChart');
        if (!chartDiv) {
            throw new Error('Chart container not found');
        }

        await Plotly.newPlot('stockChart', traces, layout, config);
        console.log('Chart created successfully');

    } catch (error) {
        console.error('Error creating chart:', error);
        const chartDiv = document.getElementById('stockChart');
        if (chartDiv) {
            chartDiv.innerHTML = `<div class="chart-error">Error loading chart: ${error.message}</div>`;
        }
    }
}

// Update chart function
function updateChart(data) {
    if (!data || !data.symbol) return;
    createStockChart(data.symbol, document.getElementById('timePeriod')?.value || '6mo');
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (document.querySelector('.stock-info')) {
        const symbol = document.querySelector('.stock-info').dataset.symbol;
        if (symbol) {
            createStockChart(symbol);
        }
    }

    // Setup chart controls
    const controls = ['chartType', 'timePeriod', 'showVolume', 'showMA', 'showBB', 'showRSI'];
    controls.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', () => {
                const symbol = document.querySelector('.stock-info')?.dataset.symbol;
                if (symbol) {
                    createStockChart(symbol, document.getElementById('timePeriod').value);
                }
            });
        }
    });
});

// Make functions available globally
window.createStockChart = createStockChart;
window.updateChart = updateChart; 
window.updateChart = updateChart; 