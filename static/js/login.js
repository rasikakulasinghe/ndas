/*
 * NDAS - Login Page JavaScript
 * Interactive functionality for the login interface
 * Created: September 24, 2025
 */

document.addEventListener('DOMContentLoaded', function() {
    // Simple password visibility toggle
    const passwordToggle = document.querySelector('.password-toggle-simple');
    const passwordField = document.querySelector('#password');
    
    if (passwordToggle && passwordField) {
        passwordToggle.addEventListener('click', function() {
            const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordField.setAttribute('type', type);
            
            const icon = this.querySelector('i');
            icon.classList.toggle('fa-eye');
            icon.classList.toggle('fa-eye-slash');
        });
    }
    
    // Simple form submission with loading state
    const loginForm = document.querySelector('#loginForm');
    const submitBtn = loginForm ? loginForm.querySelector('.simple-btn') : null;
    
    if (loginForm && submitBtn) {
        loginForm.addEventListener('submit', function(e) {
            // Add loading state
            submitBtn.classList.add('loading');
            submitBtn.disabled = true;
            submitBtn.textContent = 'Signing In...';
            
            // Re-enable button after delay for error handling
            setTimeout(() => {
                submitBtn.classList.remove('loading');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Sign In';
            }, 5000);
        });
    }
    
    // Auto-focus username field
    const usernameField = document.querySelector('#username');
    if (usernameField) {
        setTimeout(() => usernameField.focus(), 100);
    }
    
    // Enter key navigation
    document.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            const focusedElement = document.activeElement;
            if (focusedElement && focusedElement.id === 'username') {
                const passwordField = document.querySelector('#password');
                if (passwordField) {
                    passwordField.focus();
                    e.preventDefault();
                }
            } else if (focusedElement && focusedElement.id === 'password' && loginForm) {
                loginForm.submit();
            }
        }
    });
    
    // Simple input focus effects
    const inputs = document.querySelectorAll('.simple-input');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            if (this.parentElement) {
                this.parentElement.classList.add('focused');
            }
        });
        
        input.addEventListener('blur', function() {
            if (this.parentElement) {
                this.parentElement.classList.remove('focused');
            }
        });
    });
});