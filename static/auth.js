// Authentication utility functions
function isLoggedIn() {
    return localStorage.getItem('token') !== null;
}

function getAuthHeader() {
    const token = localStorage.getItem('token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

function logout() {
    localStorage.removeItem('token');
    window.location.href = '/login';
}

// Add this at the top of the file
function debug(message) {
    console.log(`[Auth Debug] ${message}`);
}

// Handle login and registration
document.addEventListener('DOMContentLoaded', function() {
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