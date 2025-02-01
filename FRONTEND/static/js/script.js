let refreshInterval;
let watchlist = new Set(JSON.parse(localStorage.getItem('watchlist') || '[]'));
let watchlistRefreshInterval;
const REFRESH_INTERVAL = 30000; // 30 seconds

// Global variables and state
let currentSymbol = '';
const defaultSymbol = 'AAPL';
let isLoading = false;

// Formatting functions
function formatNumber(num) {
    if (!num && num !== 0) return 'N/A';
    return new Intl.NumberFormat('en-US').format(num);
}

function formatPrice(price) {
    if (!price && price !== 0) return 'N/A';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(price);
}

function formatMarketCap(cap) {
    if (!cap && cap !== 0) return 'N/A';
    
    const trillion = 1e12;
    const billion = 1e9;
    const million = 1e6;

    if (cap >= trillion) {
        return `$${(cap / trillion).toFixed(2)}T`;
    } else if (cap >= billion) {
        return `$${(cap / billion).toFixed(2)}B`;
    } else if (cap >= million) {
        return `$${(cap / million).toFixed(2)}M`;
    } else {
        return `$${formatNumber(cap)}`;
    }
}

function formatPercentage(value) {
    if (!value && value !== 0) return 'N/A';
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

// Auth functions
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

function logout() {
    localStorage.removeItem('token');
    window.location.href = '/login';
}

function getToken() {
    const token = localStorage.getItem('token');
    if (!token) {
        console.log('No token found in localStorage');
        return null;
    }
    console.log('Token retrieved from localStorage:', token.substring(0, 20) + '...');
    return token;
}

function checkAuthStatus() {
    const token = localStorage.getItem('token');
    if (!token) {
        console.log('No token found');
        window.location.href = '/login';
        return false;
    }
    console.log('Token found:', token.substring(0, 20) + '...');
    return true;
}

async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('token');
    if (!token) {
        console.error('No token found');
        window.location.href = '/login';
        return null;
    }

    const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers
    };

    try {
        const response = await fetch(url, { ...options, headers });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
}

async function fetchStockData(symbol) {
    if (!symbol) {
        throw new Error('Symbol is required');
    }
    console.log('Fetching stock data for:', symbol);
    return await fetchWithAuth(`/api/stock/${symbol}`);
}

async function addToWatchlist() {
    const symbol = document.getElementById('ticker')?.value?.trim().toUpperCase();
    if (!symbol) {
        showNotification('Please enter a valid symbol', 'error');
        return;
    }

    try {
        const response = await fetch('/api/watchlist/add', {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ symbol })
        });

        if (!response.ok) {
            throw new Error('Failed to add to watchlist');
        }

        showNotification(`${symbol} added to watchlist`, 'success');
    } catch (error) {
        console.error('Error adding to watchlist:', error);
        showNotification('Failed to add to watchlist', 'error');
    }
}

async function removeFromWatchlist(symbol) {
    if (!symbol) {
        console.error('No symbol provided');
        return;
    }

    try {
        const response = await fetch('/api/watchlist/remove', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ symbol: symbol.toString().toUpperCase() })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to remove from watchlist');
        }

        // Update local watchlist
        watchlist.delete(symbol.toString().toUpperCase());
        localStorage.setItem('watchlist', JSON.stringify([...watchlist]));
        
        // Update UI
        const removeButton = document.querySelector(`[data-action="remove-from-watchlist"][data-symbol="${symbol}"]`);
        if (removeButton) {
            removeButton.textContent = 'Add to Watchlist';
            removeButton.setAttribute('data-action', 'add-to-watchlist');
        }

        showNotification('Removed from watchlist', 'success');
        
        // Refresh watchlist if on watchlist page
        if (window.location.pathname === '/watchlist') {
            await updateWatchlist();
        }

    } catch (error) {
        console.error('Error removing from watchlist:', error);
        showNotification(error.message, 'error');
    }
}

// Stock data functions
function displayStockData(data) {
    const stockData = document.getElementById('stockData');
    if (!stockData) return;

    const priceChange = data.current_price - data.previous_close;
    const changePercent = (priceChange / data.previous_close * 100);
    const changeClass = priceChange >= 0 ? 'positive-change' : 'negative-change';

    stockData.innerHTML = `
        <div class="stock-info" data-symbol="${data.symbol}">
            <h2>${data.company_name} (${data.symbol})</h2>
            <div class="price-section">
                <div class="current-price">${formatPrice(data.current_price)}</div>
                <div class="price-change ${changeClass}">
                    ${priceChange >= 0 ? '+' : ''}${formatPrice(Math.abs(priceChange))} 
                    (${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(2)}%)
                </div>
            </div>
            <div class="stock-grid">
                <div class="grid-item">
                    <span class="label">Previous Close</span>
                    <span class="value">${formatPrice(data.previous_close)}</span>
                </div>
                <div class="grid-item">
                    <span class="label">Open</span>
                    <span class="value">${formatPrice(data.open)}</span>
                </div>
                <div class="grid-item">
                    <span class="label">Day Range</span>
                    <span class="value">${formatPrice(data.day_low)} - ${formatPrice(data.day_high)}</span>
                </div>
                <div class="grid-item">
                    <span class="label">Volume</span>
                    <span class="value">${formatNumber(data.volume)}</span>
                </div>
                <div class="grid-item">
                    <span class="label">Market Cap</span>
                    <span class="value">${formatMarketCap(data.market_cap)}</span>
                </div>
                <div class="grid-item">
                    <span class="label">P/E Ratio</span>
                    <span class="value">${data.pe_ratio ? data.pe_ratio.toFixed(2) : 'N/A'}</span>
                </div>
            </div>
        </div>
    `;

    // Initialize chart
    if (typeof initializeChart === 'function') {
        initializeChart();
    }
}

// Watchlist functionality
async function updateWatchlist() {
    try {
        const response = await fetch('/api/watchlist/data', {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            throw new Error('Failed to fetch watchlist data');
        }

        const data = await response.json();
        console.log('Watchlist data:', data);

        const tbody = document.querySelector('.watchlist-table tbody');
        if (!tbody) {
            console.error('Watchlist table not found');
            return;
        }

        // Clear existing rows
        tbody.innerHTML = '';

        // Add new rows
        data.forEach(stock => {
            const row = document.createElement('tr');
            const priceChangeClass = stock.price_change >= 0 ? 'positive' : 'negative';
            
            row.innerHTML = `
                <td><a href="/quote?symbol=${stock.symbol}" class="stock-link">${stock.symbol}</a></td>
                <td>${stock.company_name || '-'}</td>
                <td>${formatPrice(stock.current_price)}</td>
                <td class="${priceChangeClass}">
                    ${formatPrice(stock.price_change)} (${stock.price_change_percent.toFixed(2)}%)
                </td>
                <td>${formatPrice(stock.previous_close)}</td>
                <td>${formatNumber(stock.volume)}</td>
                <td>${formatMarketCap(stock.market_cap)}</td>
                <td>
                    <button class="terminal-btn remove-btn" 
                            onclick="removeFromWatchlist('${stock.symbol}')">
                        REMOVE
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });

    } catch (error) {
        console.error('Error updating watchlist:', error);
        const container = document.querySelector('.watchlist-container');
        if (container) {
            container.innerHTML = `<div class="error">Error loading watchlist: ${error.message}</div>`;
        }
    }
}

// Page setup functions
function setupQuotePage() {
    const searchForm = document.getElementById('searchForm');
    const symbolInput = document.getElementById('symbolInput');

    if (searchForm) {
        searchForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const symbol = symbolInput.value.trim().toUpperCase();
            if (symbol) {
                try {
                    const data = await fetchStockData(symbol);
                    if (data) {
                        displayStockData(data);
                        // Initialize chart after displaying stock data
                        if (typeof initializeChart === 'function') {
                            await initializeChart(symbol);
                        }
                    }
                } catch (error) {
                    console.error('Error fetching stock data:', error);
                    showNotification(error.message, 'error');
                }
            }
        });
    }
}

// Auth form setup
function setupAuthForms() {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');

    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    try {
        const response = await fetch('/token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
        });

        if (!response.ok) {
            throw new Error('Login failed');
        }

        const data = await response.json();
        localStorage.setItem('token', data.access_token);
        window.location.href = '/quote';
    } catch (error) {
        showNotification('Login failed: ' + error.message, 'error');
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    try {
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, email, password })
        });

        if (!response.ok) {
            throw new Error('Registration failed');
        }

        showNotification('Registration successful! Please log in.', 'success');
        window.location.href = '/login';
    } catch (error) {
        showNotification('Registration failed: ' + error.message, 'error');
    }
}

// Chart initialization
async function initializeChart(symbol, period = '6mo') {
    try {
        const response = await fetch(`/api/stock/${symbol}/chart?period=${period}`, {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch chart data: ${response.statusText}`);
        }

        const chartData = await response.json();
        const chartContainer = document.getElementById('stockChart');
        
        if (!chartContainer) {
            console.warn('Chart container not found');
            return;
        }

        // Create the chart using createStockChart from chart.js
        if (typeof createStockChart === 'function') {
            await createStockChart(symbol);
        } else {
            console.error('createStockChart function not found');
        }
        
    } catch (error) {
        console.error('Error creating chart:', error);
        showNotification('Failed to load chart', 'error');
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', async function() {
    // Check authentication
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    try {
        // Set up event listeners
        const tickerInput = document.getElementById('ticker');
        if (tickerInput) {
            tickerInput.addEventListener('keypress', async (e) => {
                if (e.key === 'Enter') {
                    await getStockData();
                }
            });
        }

        const getQuoteBtn = document.getElementById('getQuoteBtn');
        if (getQuoteBtn) {
            getQuoteBtn.addEventListener('click', getStockData);
        }

        // Load default stock
        const defaultSymbol = 'AAPL';
        const data = await fetchStockData(defaultSymbol);
        await updateStockInfo(data);
    } catch (error) {
        console.error('Error during initialization:', error);
        showNotification('Error loading initial data', 'error');
    }
});

function setupChartControls() {
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
        const checkbox = document.getElementById(indicator);
        if (checkbox) {
            checkbox.addEventListener('change', function() {
                const symbol = document.getElementById('ticker')?.value || 'AAPL';
                toggleIndicator(indicator.toUpperCase());
                // Force chart update after toggling indicator
                if (currentChart) {
                    currentChart.update();
                }
            });
        }
    });
}

// Function to show notifications
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Make sure all necessary functions are available globally
window.logout = logout;
window.fetchStockData = fetchStockData;
window.addToWatchlist = addToWatchlist;
window.removeFromWatchlist = removeFromWatchlist;
window.updateWatchlist = updateWatchlist;
window.displayStockData = displayStockData;
window.showNotification = showNotification;
window.setupQuotePage = setupQuotePage;
window.setupAuthForms = setupAuthForms;
window.initializeChart = initializeChart;

// Function to update stock info in the UI
async function updateStockInfo(data) {
    try {
        if (!data) return;
        
        const stockData = document.getElementById('stockData');
        if (!stockData) return;
        
        // Update the stock data display
        stockData.innerHTML = `
            <div class="stock-data-section">
                <div class="stock-name">${data.company_name || data.name} (${data.symbol})</div>
                <div class="stock-price">$${data.current_price || data.price}</div>
                <div class="stock-change">${data.price_change || data.change} (${data.price_change_percent || data.changePercent}%)</div>
            </div>
            <div class="stock-data-section">
                <div class="stock-data-section-title">Market Data</div>
                <div class="stock-metrics">
                    <div class="metric">
                        <span class="metric-label">Market Cap</span>
                        <span class="metric-value">${formatLargeNumber(data.market_cap || data.marketCap)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Volume</span>
                        <span class="metric-value">${formatLargeNumber(data.volume)}</span>
                    </div>
                </div>
            </div>
        `;
        
        // Update chart with symbol
        if (data.symbol) {
            await updateChart(data.symbol);
        }
    } catch (error) {
        console.error('Error updating stock info:', error);
    }
}

// Helper function to format large numbers
function formatLargeNumber(num) {
    if (!num) return 'N/A';
    if (num >= 1e12) return (num / 1e12).toFixed(2) + 'T';
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K';
    return num.toString();
}

// Add this debug function
function debugLogStockData(data, source) {
    console.log('=== Stock Data Debug ===');
    console.log(`Source: ${source}`);
    console.log('Raw data:', data);
    
    if (data && typeof data === 'object') {
        console.log('Data properties:', Object.keys(data));
        if (data.stocks) {
            console.log('Stocks array length:', data.stocks.length);
            data.stocks.forEach((stock, index) => {
                console.log(`Stock ${index + 1} details:`, {
                    symbol: stock.symbol,
                    name: stock.company_name,
                    price: stock.current_price,
                    change: stock.price_change,
                    changePercent: stock.price_change_percent,
                    prevClose: stock.previous_close,
                    volume: stock.volume,
                    marketCap: stock.market_cap
                });
            });
        }
    }
    console.log('=== End Debug ===');
}

// Update refreshWatchlist
async function refreshWatchlist() {
    try {
        console.log('Fetching watchlist...');
        const response = await fetch('/api/watchlist/data', {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            console.error('Watchlist fetch failed:', response.status, response.statusText);
            throw new Error('Failed to fetch watchlist data');
        }

        const data = await response.json();
        debugLogStockData(data, 'Watchlist');
        updateWatchlistTable(data);
    } catch (error) {
        console.error('Error refreshing watchlist:', error);
    }
}

// Update getStockData
async function getStockData() {
    const ticker = document.getElementById('ticker').value.toUpperCase();
    if (!ticker) return;
    
    try {
        const data = await fetchStockData(ticker);
        await updateStockInfo(data);
    } catch (error) {
        console.error('Error loading stock data:', error);
        showNotification('Error loading stock data', 'error');
    }
}

// Update createStockChart to include error handling
async function createStockChart(symbol) {
    try {
        console.log('Creating chart for:', symbol);
        // ... rest of chart creation code ...
    } catch (error) {
        console.error('Error creating chart:', error);
    }
}

// Error handling
function showError(message) {
    const errorDiv = document.getElementById('errorMessage') || createErrorDiv();
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 5000);
}

function createErrorDiv() {
    const errorDiv = document.createElement('div');
    errorDiv.id = 'errorMessage';
    errorDiv.className = 'error-message';
    document.body.insertBefore(errorDiv, document.body.firstChild);
    return errorDiv;
}

// Utility functions
function formatMarketCap(marketCap) {
    if (!marketCap) return 'N/A';
    if (marketCap >= 1e12) return `$${(marketCap / 1e12).toFixed(2)}T`;
    if (marketCap >= 1e9) return `$${(marketCap / 1e9).toFixed(2)}B`;
    if (marketCap >= 1e6) return `$${(marketCap / 1e6).toFixed(2)}M`;
    return `$${marketCap.toFixed(2)}`;
}

function formatVolume(volume) {
    if (!volume) return 'N/A';
    if (volume >= 1e9) return `${(volume / 1e9).toFixed(2)}B`;
    if (volume >= 1e6) return `${(volume / 1e6).toFixed(2)}M`;
    if (volume >= 1e3) return `${(volume / 1e3).toFixed(2)}K`;
    return volume.toString();
}