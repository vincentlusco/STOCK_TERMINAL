let refreshInterval; // Store interval ID
let watchlist = new Set(JSON.parse(localStorage.getItem('watchlist') || '[]'));
let watchlistRefreshInterval;

// Move formatting functions to global scope
const formatNumber = (num) => {
    if (!num) return 'N/A';
    return num.toLocaleString('en-US');
};

const formatPrice = (price) => {
    if (!price) return 'N/A';
    
    // For penny stocks (under $1), show 4 decimal places
    // For regular stocks, show 2 decimal places
    const decimals = price < 1 ? 4 : 2;
    
    return `$${price.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    })}`;
};

const formatMarketCap = (cap) => {
    if (!cap) return 'N/A';
    if (cap >= 1e12) return `$${(cap/1e12).toFixed(2)}T`;
    if (cap >= 1e9) return `$${(cap/1e9).toFixed(2)}B`;
    if (cap >= 1e6) return `$${(cap/1e6).toFixed(2)}M`;
    return `$${cap.toLocaleString()}`;
};

function getAuthHeaders() {
    const token = localStorage.getItem('token');
    return {
        'Authorization': token ? `Bearer ${token}` : '',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'ngrok-skip-browser-warning': 'true'
    };
}

function checkAuth() {
    const token = localStorage.getItem('token');
    if (!token && window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        window.location.href = '/login';
        return false;
    }
    return true;
}

function getStockData(ticker = null) {
    if (!checkAuth()) return;
    
    // Use provided ticker or get from input
    ticker = ticker || document.getElementById("ticker").value.trim().toUpperCase();
    const stockDataDiv = document.getElementById("stockData");

    if (!ticker) {
        alert("Please enter a stock symbol!");
        return;
    }

    // Show loading state on initial load only
    if (!refreshInterval) {
        stockDataDiv.innerHTML = `<p class="loading">Loading data for ${ticker}...</p>`;
    }

    fetch(`/stock/${ticker}`, {
        method: 'GET',
        headers: getAuthHeaders()
    })
    .then(async response => {
        if (response.status === 401) {
            localStorage.removeItem('token');
            window.location.href = '/login';
            return;
        }
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to fetch stock data');
        }
        return data;
    })
    .then(data => {
        // Add last updated timestamp
        const now = new Date().toLocaleTimeString();

        // Calculate price change and percentage
        const priceChange = data.current_price - data.previous_close;
        const priceChangePercent = (priceChange / data.previous_close * 100).toFixed(2);
        const priceChangeClass = priceChange >= 0 ? 'price-up' : 'price-down';
        const priceChangeSymbol = priceChange >= 0 ? '+' : '';

        // Update stock data display
        stockDataDiv.innerHTML = `
            <div class="stock-header">
                <h2>${data.company_name} (${data.symbol})</h2>
                <div class="price-container ${priceChangeClass}">
                    <div class="current-price">${formatPrice(data.current_price)}</div>
                    <div class="price-change">
                        ${priceChangeSymbol}${formatPrice(priceChange)} (${priceChangeSymbol}${priceChangePercent}%)
                    </div>
                </div>
            </div>
            <div class="data-grid">
                <div class="data-row">
                    <div class="data-cell">
                        <div class="label">Previous Close</div>
                        <div class="value">${formatPrice(data.previous_close)}</div>
                    </div>
                    <div class="data-cell">
                        <div class="label">Open</div>
                        <div class="value">${formatPrice(data.open)}</div>
                    </div>
                    <div class="data-cell">
                        <div class="label">Day Range</div>
                        <div class="value">${formatPrice(data.day_low)} - ${formatPrice(data.day_high)}</div>
                    </div>
                </div>
                <div class="data-row">
                    <div class="data-cell">
                        <div class="label">Volume</div>
                        <div class="value">${formatNumber(data.volume)}</div>
                    </div>
                    <div class="data-cell">
                        <div class="label">Market Cap</div>
                        <div class="value">${formatMarketCap(data.market_cap)}</div>
                    </div>
                    <div class="data-cell">
                        <div class="label">P/E Ratio</div>
                        <div class="value">${data.pe_ratio ? data.pe_ratio.toFixed(2) : 'N/A'}</div>
                    </div>
                </div>
                <div class="data-row">
                    <div class="data-cell">
                        <div class="label">52 Week Range</div>
                        <div class="value">${formatPrice(data.fifty_two_week_low)} - ${formatPrice(data.fifty_two_week_high)}</div>
                    </div>
                </div>
            </div>
            <div id="chartSection" class="chart-section">
                <div id="stockChart"></div>
            </div>
            <p class="last-updated">Last Updated: ${now}</p>
        `;

        // Start auto-refresh if not already running
        if (!refreshInterval) {
            startAutoRefresh(ticker);
        }
    })
    .catch(error => {
        console.error("Error fetching stock data:", error);
        stockDataDiv.innerHTML = `
            <p style="color: red;">
                Error fetching data: ${error.message}
                <br>
                Please try again or check if the ticker symbol is correct.
            </p>
        `;
        stopAutoRefresh(); // Stop refresh on error
    });
}

// Add this function to check if user is logged in
function isLoggedIn() {
    return localStorage.getItem('token') !== null;
}

// Update the addToWatchlist function
async function addToWatchlist() {
    if (!isLoggedIn()) {
        window.location.href = '/login';
        return;
    }

    const ticker = document.getElementById("ticker").value.trim().toUpperCase();
    if (!ticker) {
        alert("Please enter a stock symbol!");
        return;
    }
    
    try {
        const response = await fetch(`/watchlist/add/${ticker}`, {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to add to watchlist');
        }
        
        alert(`Added ${ticker} to watchlist`);
        
        // If we're on the watchlist page, update it
        if (window.location.pathname === '/watchlist') {
            await updateWatchlist();
        }
    } catch (error) {
        console.error('Error:', error);
        alert(error.message);
    }
}

// Update the removeFromWatchlist function
async function removeFromWatchlist(ticker) {
    if (!isLoggedIn()) {
        window.location.href = '/login';
        return;
    }

    try {
        const response = await fetch(`/watchlist/remove/${ticker}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Failed to remove from watchlist');
        }
        
        updateWatchlist();
    } catch (error) {
        console.error('Error:', error);
        alert(error.message);
    }
}

// Update the updateWatchlist function
async function updateWatchlist() {
    if (!checkAuth()) return;
    
    const watchlistDiv = document.getElementById('watchlistContent');
    if (!watchlistDiv) return;

    try {
        console.log('Fetching watchlist...');
        const response = await fetch('/watchlist', {
            headers: getAuthHeaders()
        });
        
        console.log('Watchlist response:', response);

        if (response.status === 401) {
            localStorage.removeItem('token');
            window.location.href = '/login';
            return;
        }

        if (!response.ok) {
            throw new Error('Failed to fetch watchlist');
        }

        const watchlistData = await response.json();
        console.log('Watchlist data:', watchlistData);

        if (!watchlistData || !watchlistData.symbols || watchlistData.symbols.length === 0) {
            watchlistDiv.innerHTML = '<p style="color: #666;">No stocks in watchlist</p>';
            return;
        }

        // Then get the stock data for each symbol
        const promises = watchlistData.symbols.map(symbol => 
            fetch(`/stock/${symbol}`, {
                headers: getAuthHeaders()
            })
            .then(res => res.json())
            .then(data => {
                if (!data) throw new Error(`No data received for ${symbol}`);
                return data;
            })
            .catch(err => {
                console.error(`Error fetching ${symbol}:`, err);
                return null;
            })
        );
        
        const results = (await Promise.all(promises)).filter(data => data !== null);
        console.log('Stock data results:', results);
        
        if (results.length === 0) {
            watchlistDiv.innerHTML = '<p style="color: red;">Error loading watchlist data</p>';
            return;
        }

        // Build the watchlist table
        watchlistDiv.innerHTML = `
            <table class="watchlist-table">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Change</th>
                        <th>Volume</th>
                        <th>Market Cap</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    ${results.map(data => `
                        <tr>
                            <td>${data.symbol}</td>
                            <td>${formatPrice(data.current_price)}</td>
                            <td>${formatPriceChange(data.current_price - data.previous_close, data.previous_close)}</td>
                            <td>${formatNumber(data.volume)}</td>
                            <td>${formatMarketCap(data.market_cap)}</td>
                            <td>
                                <button onclick="removeFromWatchlist('${data.symbol}')" class="remove-btn">Remove</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            <p class="last-updated">Last Updated: ${new Date().toLocaleTimeString()}</p>
        `;
    } catch (error) {
        console.error('Error updating watchlist:', error);
        watchlistDiv.innerHTML = `<p class="error">Error: ${error.message}</p>`;
    }
}

// Helper function to format price changes
function formatPriceChange(change, basePrice) {
    const percent = (change / basePrice) * 100;
    const sign = change >= 0 ? '+' : '';
    const color = change >= 0 ? 'green' : 'red';
    return `<span style="color: ${color}">${sign}${formatPrice(change)} (${sign}${percent.toFixed(2)}%)</span>`;
}

function startAutoRefresh(ticker) {
    stopAutoRefresh();
    
    refreshInterval = setInterval(() => {
        getStockData(ticker);
    }, 30000);

    // Also start watchlist refresh if we have items
    if (watchlist.size > 0) {
        watchlistRefreshInterval = setInterval(updateWatchlist, 30000);
    }
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
    if (watchlistRefreshInterval) {
        clearInterval(watchlistRefreshInterval);
        watchlistRefreshInterval = null;
    }
}

// Update the DOMContentLoaded event listener
document.addEventListener('DOMContentLoaded', function() {
    // Check authentication first
    const token = localStorage.getItem('token');
    if (!token && window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        window.location.href = '/login';
        return;
    }

    // Get current page
    const path = window.location.pathname;
    
    if (path === '/watchlist') {
        // Initialize watchlist page
        updateWatchlist();
        watchlistRefreshInterval = setInterval(updateWatchlist, 30000);
    } else if (path === '/quote') {
        // Initialize quote page
        const tickerInput = document.getElementById('ticker');
        const quoteButton = document.querySelector('button');
        
        // Add Enter key listener for quote page
        if (tickerInput) {
            tickerInput.addEventListener('keypress', function(event) {
                if (event.key === 'Enter') {
                    stopAutoRefresh();
                    getStockData();
                }
            });
        }
        
        // Add click listener for quote button
        if (quoteButton) {
            quoteButton.addEventListener('click', function() {
                stopAutoRefresh();
                getStockData();
            });
        }
    }
    
    // Clean up intervals when leaving page
    window.addEventListener('beforeunload', function() {
        stopAutoRefresh();
    });
});

window.getStockData = getStockData;

// Add this function to draw stock charts
async function drawStockChart(ticker, chartType = 'candlestick', period = '1y', features = {}) {
    const chartDiv = document.getElementById('stockChart');
    if (!chartDiv) {
        console.error('Chart div not found');
        return;
    }

    try {
        chartDiv.innerHTML = '<p class="loading">Loading chart...</p>';
        
        const url = new URL(`/stock/${ticker}/chart`, window.location.origin);
        url.searchParams.append('chart_type', chartType);
        url.searchParams.append('period', period);
        
        // Convert boolean values to strings 'true'/'false'
        url.searchParams.append('volume', Boolean(features.volume).toString());
        url.searchParams.append('moving_average', Boolean(features.movingAverage).toString());
        url.searchParams.append('bollinger', Boolean(features.bollinger).toString());
        url.searchParams.append('rsi', Boolean(features.rsi).toString());

        console.log('Fetching chart data from:', url.toString());
        
        const response = await fetch(url, {
            headers: {
                ...getAuthHeaders(),
                'Accept': 'text/html'  // Explicitly request HTML
            }
        });
        
        if (!response.ok) {
            const error = await response.text();
            console.error('Chart error:', error);
            throw new Error('Failed to fetch chart data');
        }
        
        const chartHtml = await response.text();
        console.log('Received chart HTML length:', chartHtml.length);
        console.log('First 200 chars:', chartHtml.substring(0, 200));
        
        // Create chart container with controls
        chartDiv.innerHTML = `
            <div class="chart-controls">
                <div class="control-group">
                    <label>Chart Type:</label>
                    <select id="chartType" onchange="updateChart('${ticker}')">
                        <option value="candlestick" ${chartType === 'candlestick' ? 'selected' : ''}>Candlestick</option>
                        <option value="line" ${chartType === 'line' ? 'selected' : ''}>Line</option>
                    </select>
                </div>
                <div class="control-group">
                    <label>Time Period:</label>
                    <select id="chartPeriod" onchange="updateChart('${ticker}')">
                        <option value="1mo">1 Month</option>
                        <option value="3mo">3 Months</option>
                        <option value="6mo">6 Months</option>
                        <option value="1y" selected>1 Year</option>
                        <option value="2y">2 Years</option>
                        <option value="5y">5 Years</option>
                    </select>
                </div>
                <div class="feature-toggles">
                    <label class="toggle">
                        <input type="checkbox" id="toggleVolume" 
                            ${features.volume ? 'checked' : ''} 
                            onchange="updateChart('${ticker}')">
                        Volume
                    </label>
                    <label class="toggle">
                        <input type="checkbox" id="toggleMA" 
                            ${features.movingAverage ? 'checked' : ''} 
                            onchange="updateChart('${ticker}')">
                        Moving Averages
                    </label>
                    <label class="toggle">
                        <input type="checkbox" id="toggleBollinger" 
                            ${features.bollinger ? 'checked' : ''} 
                            onchange="updateChart('${ticker}')">
                        Bollinger Bands
                    </label>
                    <label class="toggle">
                        <input type="checkbox" id="toggleRSI" 
                            ${features.rsi ? 'checked' : ''} 
                            onchange="updateChart('${ticker}')">
                        RSI
                    </label>
                </div>
            </div>
            <div id="plotly-chart-container" class="chart-container"></div>
        `;

        // Get the container and insert the chart HTML
        const plotlyContainer = document.getElementById('plotly-chart-container');
        if (plotlyContainer) {
            plotlyContainer.innerHTML = chartHtml;
            
            // Force a reflow
            void plotlyContainer.offsetHeight;
            
            // Make sure Plotly is loaded
            if (typeof Plotly !== 'undefined') {
                const plotlyDiv = plotlyContainer.querySelector('.js-plotly-plot');
                if (plotlyDiv) {
                    // Trigger a window resize to make Plotly redraw
                    window.dispatchEvent(new Event('resize'));
                }
            }
        }

    } catch (error) {
        console.error('Error drawing chart:', error);
        chartDiv.innerHTML = `<p class="error">Failed to load chart: ${error.message}</p>`;
    }
}

async function updateChart(ticker) {
    const chartType = document.getElementById('chartType').value;
    const period = document.getElementById('chartPeriod').value;
    const features = {
        volume: document.getElementById('toggleVolume')?.checked || false,
        movingAverage: document.getElementById('toggleMA')?.checked || false,
        bollinger: document.getElementById('toggleBollinger')?.checked || false,
        rsi: document.getElementById('toggleRSI')?.checked || false
    };
    await drawStockChart(ticker, chartType, period, features);
}

// Update getStockData to include chart
async function getStockData() {
    const ticker = document.getElementById("ticker").value.trim().toUpperCase();
    const stockDataDiv = document.getElementById("stockData");

    if (!ticker) {
        alert("Please enter a stock symbol!");
        return;
    }

    stockDataDiv.innerHTML = '<p class="loading">Loading data...</p>';

    try {
        const response = await fetch(`/stock/${ticker}`, {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            throw new Error('Failed to fetch stock data');
        }

        const data = await response.json();
        
        // Calculate price change and percentage
        const priceChange = data.current_price - data.previous_close;
        const priceChangePercent = (priceChange / data.previous_close * 100).toFixed(2);
        const priceChangeClass = priceChange >= 0 ? 'price-up' : 'price-down';
        const priceChangeSymbol = priceChange >= 0 ? '+' : '';

        // Update stock data display
        stockDataDiv.innerHTML = `
            <div class="stock-header">
                <h2>${data.company_name} (${data.symbol})</h2>
                <div class="price-container ${priceChangeClass}">
                    <div class="current-price">${formatPrice(data.current_price)}</div>
                    <div class="price-change">
                        ${priceChangeSymbol}${formatPrice(priceChange)} (${priceChangeSymbol}${priceChangePercent}%)
                    </div>
                </div>
            </div>
            <div class="data-grid">
                <div class="data-row">
                    <div class="data-cell">
                        <div class="label">Previous Close</div>
                        <div class="value">${formatPrice(data.previous_close)}</div>
                    </div>
                    <div class="data-cell">
                        <div class="label">Open</div>
                        <div class="value">${formatPrice(data.open)}</div>
                    </div>
                    <div class="data-cell">
                        <div class="label">Day Range</div>
                        <div class="value">${formatPrice(data.day_low)} - ${formatPrice(data.day_high)}</div>
                    </div>
                </div>
                <div class="data-row">
                    <div class="data-cell">
                        <div class="label">Volume</div>
                        <div class="value">${formatNumber(data.volume)}</div>
                    </div>
                    <div class="data-cell">
                        <div class="label">Market Cap</div>
                        <div class="value">${formatMarketCap(data.market_cap)}</div>
                    </div>
                    <div class="data-cell">
                        <div class="label">P/E Ratio</div>
                        <div class="value">${data.pe_ratio ? data.pe_ratio.toFixed(2) : 'N/A'}</div>
                    </div>
                </div>
                <div class="data-row">
                    <div class="data-cell">
                        <div class="label">52 Week Range</div>
                        <div class="value">${formatPrice(data.fifty_two_week_low)} - ${formatPrice(data.fifty_two_week_high)}</div>
                    </div>
                </div>
            </div>
            <div id="chartSection" class="chart-section">
                <div id="stockChart"></div>
            </div>
        `;

        // Draw the chart
        await drawStockChart(ticker);
        
        // Start auto-refresh
        startAutoRefresh(ticker);
    } catch (error) {
        console.error('Error:', error);
        stockDataDiv.innerHTML = `<p class="error">Error: ${error.message}</p>`;
    }
}