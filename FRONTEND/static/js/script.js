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

async function addToWatchlist(symbol) {
    if (!symbol) {
        console.error('No symbol provided');
        return;
    }

    try {
        const response = await fetch('/api/watchlist/add', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ symbol: symbol.toString().toUpperCase() })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add to watchlist');
        }

        // Update local watchlist
        watchlist.add(symbol.toString().toUpperCase());
        localStorage.setItem('watchlist', JSON.stringify([...watchlist]));
        
        // Update UI
        const addButton = document.querySelector(`[data-action="add-to-watchlist"][data-symbol="${symbol}"]`);
        if (addButton) {
            addButton.textContent = 'Remove from Watchlist';
            addButton.setAttribute('data-action', 'remove-from-watchlist');
        }

        showNotification('Added to watchlist', 'success');
        
        // Refresh watchlist if on watchlist page
        if (window.location.pathname === '/watchlist') {
            await updateWatchlist();
        }

    } catch (error) {
        console.error('Error adding to watchlist:', error);
        showNotification(error.message, 'error');
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

        // Create the chart using the data
        // Note: This assumes you're using a charting library
        // Implementation will depend on your chosen library
        
    } catch (error) {
        console.error('Error creating chart:', error);
        showNotification('Failed to load chart', 'error');
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    if (!checkAuth()) return;

    const path = window.location.pathname;
    
    if (path === '/watchlist') {
        updateWatchlist();
        watchlistRefreshInterval = setInterval(updateWatchlist, REFRESH_INTERVAL);
    } else if (path === '/quote') {
        setupQuotePage();
    }

    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const symbol = document.getElementById('symbol').value.toUpperCase();
            try {
                const data = await fetchStockData(symbol);
                updateStockInfo(data);
                updateChart(data);
            } catch (error) {
                console.error('Error:', error);
                alert('Error fetching stock data');
            }
        });
    }

    // Add click handlers for quick search buttons
    const quickSearchButtons = document.querySelectorAll('.quick-search');
    quickSearchButtons.forEach(button => {
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            const symbol = this.getAttribute('data-symbol');
            if (!symbol) {
                console.error('No symbol found on button');
                return;
            }
            try {
                const data = await fetchStockData(symbol);
                updateStockInfo(data);
                updateChart(data);
            } catch (error) {
                console.error('Error:', error);
                alert('Error fetching stock data');
            }
        });
    });

    // Load default stock (AAPL) on page load
    if (window.location.pathname === '/quote') {
        fetchStockData('AAPL')
            .then(data => {
                updateStockInfo(data);
                updateChart(data);
            })
            .catch(error => {
                console.error('Error loading default stock:', error);
            });
    }

    // Setup page specific functionality
    if (window.location.pathname === '/quote') {
        setupQuotePage();
    }
    if (window.location.pathname === '/login' || window.location.pathname === '/register') {
        setupAuthForms();
    }

    // Add click handler for watchlist buttons
    document.addEventListener('click', async function(event) {
        const button = event.target;
        if (button.hasAttribute('data-action') && button.hasAttribute('data-symbol')) {
            const action = button.getAttribute('data-action');
            const symbol = button.getAttribute('data-symbol');
            
            try {
                if (action === 'add-to-watchlist') {
                    await addToWatchlist(symbol);
                } else if (action === 'remove-from-watchlist') {
                    await removeFromWatchlist(symbol);
                }
            } catch (error) {
                console.error('Error with watchlist action:', error);
                showNotification(error.message, 'error');
            }
        }
    });
});

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
function updateStockInfo(data) {
    if (!data) return;
    
    const stockData = document.getElementById('stockData');
    if (!stockData) return;

    const stockInfo = document.createElement('div');
    stockInfo.className = 'stock-info';
    stockInfo.dataset.symbol = data.symbol;

    // Format price change percentage with fallback
    const priceChangePercent = data.price_change_percent !== undefined ? 
        data.price_change_percent.toFixed(2) : '0.00';
    
    // Format price change with fallback
    const priceChange = data.price_change !== undefined ? 
        formatPrice(data.price_change) : '0.00';

    stockInfo.innerHTML = `
        <h2>${data.company_name || ''} (${data.symbol || ''})</h2>
        <div class="price-info">
            <div class="current-price">${formatPrice(data.current_price) || 'N/A'}</div>
            <div class="price-change ${(data.price_change || 0) >= 0 ? 'positive' : 'negative'}">
                ${priceChange} (${priceChangePercent}%)
            </div>
        </div>
        <div class="stock-details">
            <div>Market Cap: ${formatMarketCap(data.market_cap)}</div>
            <div>Volume: ${formatNumber(data.volume)}</div>
            <div>52W High: ${formatPrice(data.fifty_two_week_high) || 'N/A'}</div>
            <div>52W Low: ${formatPrice(data.fifty_two_week_low) || 'N/A'}</div>
        </div>
    `;

    stockData.innerHTML = '';
    stockData.appendChild(stockInfo);

    // Update chart after updating stock info
    if (typeof updateChart === 'function') {
        updateChart(data);
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
async function getStockData(symbol = null) {
    try {
        symbol = symbol || document.getElementById('ticker').value?.toUpperCase();
        if (!symbol) {
            console.log('No symbol provided');
            return;
        }

        console.log('Fetching stock data for:', symbol);
        const response = await fetch(`/api/stock/${symbol}`, {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            console.error('Stock fetch failed:', response.status, response.statusText);
            throw new Error(`Failed to fetch stock data for ${symbol}`);
        }

        const data = await response.json();
        debugLogStockData(data, 'Single Stock');
        
        updateStockInfo(data);
        // Only create chart if we have valid data
        if (data && data.symbol) {
            createStockChart(symbol);
        }
    } catch (error) {
        console.error('Error loading stock:', error);
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

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if we have a token
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/login';
    }
});

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

// Event handlers
document.getElementById('stockSymbol')?.addEventListener('keypress', async (e) => {
    if (e.key === 'Enter') {
        const symbol = e.target.value.toUpperCase();
        await updateStockDisplay(symbol);
    }
});

document.getElementById('getQuoteBtn')?.addEventListener('click', async () => {
    const symbol = document.getElementById('stockSymbol').value.toUpperCase();
    await updateStockDisplay(symbol);
});

// Initialize with default stock
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await updateStockDisplay(defaultSymbol);
    } catch (error) {
        console.error('Error loading default stock:', error);
        showError('Error loading default stock data');
    }
});

// Export functions for use in other scripts
window.updateStockDisplay = updateStockDisplay;
window.showError = showError;

// Immediately declare all functions at the top
const stockService = {
    // State
    currentSymbol: '',
    defaultSymbol: 'AAPL',
    isLoading: false,

    // Core functions
    async init() {
        this.attachEventListeners();
        await this.loadDefaultStock();
    },

    attachEventListeners() {
        const symbolInput = document.getElementById('stockSymbol');
        const quoteButton = document.getElementById('getQuoteBtn');

        if (symbolInput) {
            symbolInput.addEventListener('keypress', async (e) => {
                if (e.key === 'Enter') {
                    const symbol = e.target.value.toUpperCase();
                    await this.updateStockDisplay(symbol);
                }
            });
        }

        if (quoteButton) {
            quoteButton.addEventListener('click', async () => {
                const symbol = document.getElementById('stockSymbol')?.value.toUpperCase();
                if (symbol) {
                    await this.updateStockDisplay(symbol);
                }
            });
        }
    },

    async loadDefaultStock() {
        try {
            await this.updateStockDisplay(this.defaultSymbol);
        } catch (error) {
            console.error('Error loading default stock:', error);
            this.showError('Error loading default stock data');
        }
    },

    // API functions
    async fetchWithAuth(url, options = {}) {
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
    },

    async fetchStockData(symbol) {
        if (!symbol) {
            throw new Error('Symbol is required');
        }
        console.log('Fetching stock data for:', symbol);
        return await this.fetchWithAuth(`/api/stock/${symbol}`);
    },

    // UI update functions
    async updateStockDisplay(symbol) {
        if (this.isLoading) return;
        
        try {
            this.isLoading = true;
            console.log('Fetching stock data for:', symbol);
            
            const data = await this.fetchStockData(symbol);
            if (!data) {
                throw new Error('No data received');
            }

            this.currentSymbol = symbol;
            document.getElementById('stockSymbol').value = symbol;
            
            // Update stock info display
            const stockInfo = document.getElementById('stockInfo');
            if (stockInfo) {
                const priceChangeClass = data.price_change >= 0 ? 'positive' : 'negative';
                const priceChangeSign = data.price_change >= 0 ? '+' : '';

                stockInfo.innerHTML = `
                    <div class="stock-header">
                        <h2>${data.company_name} (${data.symbol})</h2>
                    </div>
                    <div class="stock-price">
                        <span class="current-price">$${data.current_price.toFixed(2)}</span>
                        <span class="price-change ${priceChangeClass}">
                            ${priceChangeSign}$${data.price_change.toFixed(2)} 
                            (${priceChangeSign}${data.price_change_percent.toFixed(2)}%)
                        </span>
                    </div>
                    <div class="stock-details">
                        <div>Market Cap: ${this.formatMarketCap(data.market_cap)}</div>
                        <div>Volume: ${this.formatVolume(data.volume)}</div>
                        <div>52W High: $${data['52w_high']}</div>
                        <div>52W Low: $${data['52w_low']}</div>
                    </div>
                `;
            }

            // Update chart
            if (typeof window.createStockChart === 'function') {
                await window.createStockChart(symbol);
            }

        } catch (error) {
            console.error('Error updating stock display:', error);
            this.showError(`Error loading stock data: ${error.message}`);
        } finally {
            this.isLoading = false;
        }
    },

    formatMarketCap(marketCap) {
        if (!marketCap) return 'N/A';
        if (marketCap >= 1e12) return `$${(marketCap / 1e12).toFixed(2)}T`;
        if (marketCap >= 1e9) return `$${(marketCap / 1e9).toFixed(2)}B`;
        if (marketCap >= 1e6) return `$${(marketCap / 1e6).toFixed(2)}M`;
        return `$${marketCap.toFixed(2)}`;
    },

    formatVolume(volume) {
        if (!volume) return 'N/A';
        if (volume >= 1e9) return `${(volume / 1e9).toFixed(2)}B`;
        if (volume >= 1e6) return `${(volume / 1e6).toFixed(2)}M`;
        if (volume >= 1e3) return `${(volume / 1e3).toFixed(2)}K`;
        return volume.toString();
    },

    showError(message) {
        const errorDiv = document.getElementById('errorMessage') || this.createErrorDiv();
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    },

    createErrorDiv() {
        const errorDiv = document.createElement('div');
        errorDiv.id = 'errorMessage';
        errorDiv.className = 'error-message';
        document.body.insertBefore(errorDiv, document.body.firstChild);
        return errorDiv;
    }
};

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    const symbolInput = document.getElementById('stockSymbol');
    const quoteButton = document.getElementById('getQuoteBtn');

    if (symbolInput) {
        symbolInput.addEventListener('keypress', async (e) => {
            if (e.key === 'Enter') {
                const symbol = e.target.value.toUpperCase();
                await stockService.updateStockDisplay(symbol);
            }
        });
    }

    if (quoteButton) {
        quoteButton.addEventListener('click', async () => {
            const symbol = document.getElementById('stockSymbol')?.value.toUpperCase();
            if (symbol) {
                await stockService.updateStockDisplay(symbol);
            }
        });
    }

    // Load default stock
    stockService.updateStockDisplay(stockService.defaultSymbol).catch(error => {
        console.error('Error loading default stock:', error);
        stockService.showError('Error loading default stock data');
    });
});

// Export functions for use in other scripts
window.updateStockDisplay = (symbol) => stockService.updateStockDisplay(symbol);
window.showError = (message) => stockService.showError(message);