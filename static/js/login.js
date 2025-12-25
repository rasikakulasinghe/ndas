/*
 * NDAS - Login Page JavaScript
 * Interactive functionality for the login interface
 * Updated: November 6, 2025
 */

// Password visibility toggle function
function togglePasswordVisibility() {
    const passwordField = document.querySelector('#password');
    const passwordToggle = document.querySelector('.ndas-password-toggle');

    if (passwordField && passwordToggle) {
        const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordField.setAttribute('type', type);

        // Toggle between eye and eye-slash SVG icons
        const svgIcon = passwordToggle.querySelector('svg');
        if (type === 'text') {
            // Eye slash icon (password visible)
            svgIcon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';
        } else {
            // Eye icon (password hidden)
            svgIcon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Password visibility toggle - attach event listener
    const passwordToggleBtn = document.querySelector('#passwordToggleBtn');
    if (passwordToggleBtn) {
        passwordToggleBtn.addEventListener('click', togglePasswordVisibility);
    }

    // Form submission with loading state
    const loginForm = document.querySelector('#loginForm');
    const submitBtn = loginForm ? loginForm.querySelector('.ndas-signin-btn') : null;

    if (loginForm && submitBtn) {
        loginForm.addEventListener('submit', function(e) {
            // Add loading state
            submitBtn.classList.add('loading');
            submitBtn.disabled = true;
            const originalText = submitBtn.textContent;
            submitBtn.textContent = 'Signing In...';

            // Re-enable button after delay for error handling
            setTimeout(() => {
                submitBtn.classList.remove('loading');
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }, 5000);
        });
    }

    // Auto-focus username field
    const usernameField = document.querySelector('#username');
    if (usernameField) {
        setTimeout(() => usernameField.focus(), 100);
    }

    // Enhanced keyboard navigation
    const passwordField = document.querySelector('#password');

    if (usernameField && passwordField) {
        usernameField.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                passwordField.focus();
            }
        });

        passwordField.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && loginForm) {
                e.preventDefault();
                loginForm.submit();
            }
        });
    }

    // Input focus effects
    const inputs = document.querySelectorAll('.ndas-input');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
        });

        input.addEventListener('blur', function() {
            this.parentElement.classList.remove('focused');
        });
    });

    // Prevent form resubmission on page refresh
    if (window.history.replaceState) {
        window.history.replaceState(null, null, window.location.href);
    }

    // Contact Developer Modal Enhancements
    const contactModal = document.getElementById('contactDeveloperModal');

    if (contactModal) {
        // Track focus for return after close
        let modalTrigger = null;

        // On modal show
        $(contactModal).on('show.bs.modal', function(e) {
            // Store the element that triggered the modal
            modalTrigger = e.relatedTarget || document.activeElement;
        });

        // On modal shown (after animation complete)
        $(contactModal).on('shown.bs.modal', function() {
            // Focus on first focusable element or close button
            const firstFocusable = contactModal.querySelector('button[data-dismiss="modal"]');
            if (firstFocusable) {
                firstFocusable.focus();
            }

            // Initialize tooltips for social media icons
            $('[data-toggle="tooltip"]').tooltip({
                trigger: 'hover',
                boundary: 'window',
                animation: true
            });
        });

        // On modal hidden (after close animation)
        $(contactModal).on('hidden.bs.modal', function() {
            // Destroy tooltips to prevent memory leaks
            $('[data-toggle="tooltip"]').tooltip('dispose');

            // Return focus to trigger element
            if (modalTrigger && modalTrigger.focus) {
                modalTrigger.focus();
            }
        });

        // Ensure all external links have proper attributes
        const externalLinks = contactModal.querySelectorAll('a[target="_blank"]');
        externalLinks.forEach(link => {
            if (!link.getAttribute('rel')) {
                link.setAttribute('rel', 'noopener noreferrer');
            }
        });
    }
});
