function updateNav() {
    const nav = document.querySelector('.terminal-nav');
    if (!nav) return;

    const isLoggedIn = localStorage.getItem('token') !== null;
    const currentPath = window.location.pathname;

    // Don't show nav on login/register pages
    if (currentPath === '/login' || currentPath === '/register') {
        nav.style.display = 'none';
        return;
    }

    nav.style.display = 'flex';
    nav.innerHTML = `
        <div class="nav-links">
            <a href="/quote" class="nav-btn ${currentPath === '/quote' ? 'active' : ''}">QUOTES</a>
            <a href="/watchlist" class="nav-btn ${currentPath === '/watchlist' ? 'active' : ''}">WATCHLIST</a>
        </div>
        <div class="nav-auth">
            ${isLoggedIn ? 
                `<button onclick="logout()" class="nav-btn nav-btn-logout">LOGOUT</button>` : 
                `<a href="/login" class="nav-btn">LOGIN</a>`
            }
        </div>
    `;
}

function logout() {
    localStorage.removeItem('token');
    window.location.href = '/login';
}

// Update nav when page loads and when route changes
document.addEventListener('DOMContentLoaded', updateNav);
window.addEventListener('popstate', updateNav); 