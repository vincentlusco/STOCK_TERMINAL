let refreshInterval;
let watchlist = new Set(JSON.parse(localStorage.getItem('watchlist') || '[]'));
let watchlistRefreshInterval;
const REFRESH_INTERVAL = 30000; // 30 seconds

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

async function fetchStockData(symbol) {
    if (!checkAuthStatus()) return;
    
    try {
        const response = await fetch(`/api/stock/${symbol}`, {
            headers: getAuthHeaders()
        });
        
        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error fetching stock data:', error);
        throw error;
    }
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
        loginForm.addEventListener('submit', async function(e) {
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
        });
    }

    if (registerForm) {
        registerForm.addEventListener('submit', async function(e) {
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
        });
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
            <div>Market Cap: ${formatMarketCap(data.market_cap) || 'N/A'}</div>
            <div>Volume: ${formatNumber(data.volume) || 'N/A'}</div>
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