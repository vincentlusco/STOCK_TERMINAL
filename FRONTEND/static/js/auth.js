// Authentication utility functions
function isLoggedIn() {
    return localStorage.getItem('token') !== null;
}

function getAuthHeader() {
    const token = localStorage.getItem('token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

function logout() {
    console.log('Logging out - clearing token');
    localStorage.removeItem('token');
    window.location.href = '/login';
}

// Add this at the top of the file
function debug(message) {
    console.log(`[Auth Debug] ${message}`);
}

// Function to validate token
async function validateToken() {
    const token = localStorage.getItem('token');
    if (!token) {
        return false;
    }

    try {
        const response = await fetch('/api/validate-token', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error('Token validation failed');
        }

        const data = await response.json();
        return data.valid;
    } catch (error) {
        console.error('Error validating token:', error);
        return false;
    }
}

// Handle login and registration
document.addEventListener('DOMContentLoaded', async function() {
    // If we're not on the login or register page
    if (!window.location.pathname.includes('/login') && 
        !window.location.pathname.includes('/register')) {
        
        const isValid = await validateToken();
        if (!isValid) {
            logout();
            return;
        }
    }

    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');

    // Check login status and update UI
    if (isLoggedIn()) {
        fetch('/api/user/profile', {
            headers: getAuthHeader()
        })
        .then(res => res.json())
        .then(user => {
            const usernameDisplay = document.getElementById('username-display');
            if (usernameDisplay) {
                usernameDisplay.textContent = user.username;
            }
        })
        .catch(console.error);
    }

    if (loginForm) {
        loginForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            debug('Login form submitted');
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;

            try {
                debug('Sending login request...');
                const response = await fetch('/token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
                });

                debug(`Login response status: ${response.status}`);
                const data = await response.json();
                debug(`Login response data: ${JSON.stringify(data)}`);

                if (response.ok) {
                    console.log('Login successful');
                    console.log('Token:', data.access_token);
                    debug('Login successful, storing token...');
                    localStorage.setItem('token', data.access_token);
                    
                    // Make an authenticated request to /quote
                    debug('Making authenticated request to /quote...');
                    const quoteResponse = await fetch('/quote', {
                        headers: {
                            'Authorization': `Bearer ${data.access_token}`
                        }
                    });
                    
                    if (quoteResponse.ok) {
                        window.location.href = '/quote';
                    } else {
                        throw new Error('Failed to access quote page');
                    }
                } else {
                    console.error('Login failed:', data.detail);
                    throw new Error(data.detail || 'Login failed');
                }
            } catch (error) {
                console.error('Login error:', error);
                showError(error.message);
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
                const response = await fetch('/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        username: username,
                        email: email,
                        password: password
                    })
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Registration failed');
                }

                // Registration successful
                window.location.href = '/login';
            } catch (error) {
                showError(error.message);
            }
        });
    }
});

function showError(message) {
    let errorDiv = document.querySelector('.error-message');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        const form = document.querySelector('form');
        form.insertBefore(errorDiv, form.firstChild);
    }
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

// Remove duplicate register function and consolidate into one
async function register(username, email, password) {
    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, email, password })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Registration failed');
        }

        window.location.href = '/login';
    } catch (error) {
        console.error('Registration error:', error);
        throw error;
    }
}

// Function to handle login
async function login() {
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
        console.error('Login error:', error);
        alert('Login failed');
    }
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

// Check token validity on page load
document.addEventListener('DOMContentLoaded', async function() {
    const isValid = await validateToken();
    if (!isValid && window.location.pathname !== '/login') {
        window.location.href = '/login';
    }
});

// Auth utility functions
function getAuthHeaders() {
    const token = localStorage.getItem('token');
    return {
        'Authorization': token ? `Bearer ${token}` : '',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    };
}

function checkAuthStatus() {
    const token = localStorage.getItem('token');
    if (!token && !window.location.pathname.includes('/login')) {
        window.location.href = '/login';
        return false;
    }
    return true;
}

async function validateToken() {
    const token = localStorage.getItem('token');
    if (!token) return false;

    try {
        const response = await fetch('/api/validate-token', {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            throw new Error('Token validation failed');
        }

        const data = await response.json();
        return data.valid;
    } catch (error) {
        console.error('Error validating token:', error);
        return false;
    }
}

async function login(username, password) {
    try {
        const response = await fetch('/token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }

        const data = await response.json();
        localStorage.setItem('token', data.access_token);
        window.location.href = '/quote';
    } catch (error) {
        console.error('Login error:', error);
        throw error;
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', async function() {
    if (!window.location.pathname.includes('/login') && 
        !window.location.pathname.includes('/register')) {
        
        const isValid = await validateToken();
        if (!isValid) {
            logout();
            return;
        }
    }

    setupAuthForms();
});

// Make functions available globally
window.login = login;
window.register = register;
window.logout = logout;
window.checkAuthStatus = checkAuthStatus;
window.getAuthHeaders = getAuthHeaders; 