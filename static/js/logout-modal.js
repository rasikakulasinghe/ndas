/**
 * NDAS Professional Logout Modal
 * Handles logout confirmation with enhanced UX
 * Version: 2.0 - Optimized (reduced console logging)
 */

(function() {
    'use strict';

    // Wait for DOM and dependencies
    function initLogoutModal() {
        // Check for jQuery
        if (typeof $ === 'undefined') {
            setTimeout(initLogoutModal, 100);
            return;
        }

        /**
         * Show logout confirmation modal
         */
        window.showLogoutConfirmation = function() {
            var modal = $('#logoutModal');
            if (modal.length) {
                modal.modal({
                    backdrop: 'static',
                    keyboard: true,
                    focus: true
                });

                // Add entrance animation
                setTimeout(function() {
                    modal.find('.professional-logout-modal').addClass('modal-entered');
                }, 50);
            } else {
                // Fallback to native confirm dialog
                if (confirm('Are you sure you want to logout?\nYour session will be terminated and any unsaved work will be lost.')) {
                    window.location.href = modal.data('logout-url') || '/users/logout/';
                }
            }
        };

        // Handle logout confirmation clicks (event delegation)
        $(document).off('click.logoutConfirm').on('click.logoutConfirm', '.logout-confirm', function(e) {
            e.preventDefault();
            e.stopPropagation();
            showLogoutConfirmation();
            return false;
        });

        // Handle logout button with loading state
        $(document).off('click.logoutBtn').on('click.logoutBtn', '.logout-confirm-btn', function(e) {
            e.preventDefault();
            var btn = $(this);
            var logoutUrl = btn.attr('href');

            // Add loading state
            btn.html('<i class="fas fa-spinner fa-spin mr-2"></i>Terminating Session...')
               .addClass('loading disabled')
               .attr('disabled', true);

            $('#logoutModal .professional-logout-modal').addClass('modal-processing');

            // Redirect after animation
            setTimeout(function() {
                window.location.href = logoutUrl;
            }, 1200);

            return false;
        });

        // Focus management for accessibility
        $('#logoutModal').on('shown.bs.modal', function() {
            var primaryBtn = $(this).find('.btn-danger');
            if (primaryBtn.length) {
                setTimeout(function() {
                    primaryBtn.focus();
                }, 300);
            }
        });

        // Keyboard shortcuts
        $(document).on('keydown', function(e) {
            if ($('#logoutModal').hasClass('show')) {
                if (e.keyCode === 13) { // Enter key
                    e.preventDefault();
                    $('.logout-confirm-btn').click();
                }
            }
        });

        // Modal lifecycle events
        $('#logoutModal')
            .on('show.bs.modal', function() {
                $('body').addClass('modal-opening');
            })
            .on('shown.bs.modal', function() {
                $('body').removeClass('modal-opening').addClass('modal-open-professional');
            })
            .on('hide.bs.modal', function() {
                $('body').removeClass('modal-open-professional').addClass('modal-closing');
            })
            .on('hidden.bs.modal', function() {
                $('body').removeClass('modal-closing');
                // Reset loading states
                var btn = $(this).find('.logout-confirm-btn');
                btn.removeClass('loading disabled').removeAttr('disabled');
                $(this).find('.professional-logout-modal').removeClass('modal-processing');
            });

        // Hover effects
        $('#logoutModal').on('mouseenter', '.btn', function() {
            $(this).addClass('btn-hover-enhanced');
        }).on('mouseleave', '.btn', function() {
            $(this).removeClass('btn-hover-enhanced');
        });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLogoutModal);
    } else {
        initLogoutModal();
    }

    // Fallback function (if modal not available)
    window.showLogoutConfirmation = window.showLogoutConfirmation || function() {
        if (confirm('Are you sure you want to logout?')) {
            window.location.href = '/users/logout/';
        }
    };

})();

// Add enhancement styles dynamically
if (!document.getElementById('logout-modal-enhancements')) {
    var style = document.createElement('style');
    style.id = 'logout-modal-enhancements';
    style.textContent = `
        .professional-focus-enhanced {
            box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.25) !important;
            transform: scale(1.02) !important;
        }
        .btn-hover-enhanced {
            transform: translateY(-1px) scale(1.02) !important;
        }
        .modal-processing {
            pointer-events: none;
            opacity: 0.9;
        }
        .modal-processing::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(1px);
            border-radius: 18px;
        }
        body.modal-opening,
        body.modal-open-professional,
        body.modal-closing {
            overflow: hidden;
        }
    `;
    document.head.appendChild(style);
}
