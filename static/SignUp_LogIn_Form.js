const container = document.querySelector('.container');
const registerBtn = document.querySelector('.register-btn');
const loginBtn = document.querySelector('.login-btn');

// Toggle animation between login and register
registerBtn.addEventListener('click', () => {
    container.classList.add('active');
});
loginBtn.addEventListener('click', () => {
    container.classList.remove('active');
});

// ===== Handle Registration =====
const registerForm = document.querySelector('.form-box.register form');
registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(registerForm);

    try {
        const res = await fetch('/register', {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' } // important for Flask
        });

        const data = await res.json();
        alert(data.message); // show message as alert

        if (data.status === "success") {
            container.classList.remove('active'); // switch to login form
            registerForm.reset();
        }
    } catch (err) {
        console.error("Error:", err);
        alert("Server error. Please try again later.");
    }
});

// ===== Handle Login =====
const loginForm = document.querySelector('.form-box.login form');
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(loginForm);

    try {
        const res = await fetch('/login', {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' } // important for Flask
        });

        const data = await res.json();
        alert(data.message); // show message as alert

        if (data.status === "success") {
            window.location.href = data.redirect; // redirect to dashboard
        }
    } catch (err) {
        console.error("Error:", err);
        alert("Server error. Please try again later.");
    }
});


