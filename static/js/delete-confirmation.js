/**
 * NDAS Unified Delete Confirmation System
 * File: static/js/delete-confirmation.js
 * Part of refactor-delete-confirmation change
 *
 * Provides consistent deletion behavior with password verification
 * across all entity types in the NDAS application.
 */
(function() {
    'use strict';

    /**
     * DeleteConfirmation - Singleton module for handling entity deletions
     * @namespace
     */
    window.DeleteConfirmation = {
        /**
         * Show deletion modal with entity-specific configuration
         * @param {string} modalId - Modal DOM ID (e.g., 'deletePatientModal')
         * @param {Object} config - Optional configuration object
         * @param {string} config.entityType - Type of entity being deleted
         * @param {string} config.entityName - Name/identifier of entity
         */
        show: function(modalId, config) {
            console.log('DeleteConfirmation.show() called with modalId:', modalId);
            const modal = $('#' + modalId);

            if (modal.length === 0) {
                console.error('DeleteConfirmation: Modal not found with ID:', modalId);
                console.error('DeleteConfirmation: Available modals:', $('[id*="Modal"]').map(function() { return this.id; }).get());

                // Show user-friendly error
                if (typeof window.showAlert === 'function') {
                    window.showAlert('Error: Delete modal not found. Please refresh the page and try again.', 'danger');
                } else {
                    alert('Error: Delete confirmation modal not found. Please refresh the page and try again.');
                }
                return;
            }

            console.log('DeleteConfirmation: Modal found, element:', modal[0]);

            // Store configuration if provided
            if (config) {
                modal.data('delete-config', config);
            }

            // Clear previous state
            const passwordFieldId = 'deletePassword' + modalId;
            const passwordField = $('#' + passwordFieldId);
            const errorDiv = $('#deleteError' + modalId);

            console.log('DeleteConfirmation: Looking for password field with ID:', passwordFieldId);
            console.log('DeleteConfirmation: Password field found:', passwordField.length > 0);

            if (passwordField.length === 0) {
                console.error('DeleteConfirmation: Password field not found for modal:', modalId);
                console.error('DeleteConfirmation: Expected password field ID:', passwordFieldId);
                console.error('DeleteConfirmation: Available password fields:', $('[id*="deletePassword"]').map(function() { return this.id; }).get());
                alert('Error: Password field not found in delete modal. Modal ID: ' + modalId + ', Expected field ID: ' + passwordFieldId);
                return;
            }

            passwordField.val('');
            errorDiv.hide().text('');

            // Enable delete button
            const deleteBtn = $('#confirmDeleteBtn' + modalId);
            if (deleteBtn.length > 0) {
                deleteBtn.prop('disabled', false);
                deleteBtn.find('.spinner-border').hide();
            } else {
                console.warn('DeleteConfirmation: Delete button not found for modal:', modalId);
            }

            // Show modal
            modal.modal('show');

            // Focus password field after modal is shown
            modal.one('shown.bs.modal', function() {
                passwordField.focus();
            });
        },

        /**
         * Execute deletion after password verification
         * @param {HTMLElement} button - Delete button element with data attributes
         */
        execute: function(button) {
            const deleteBtn = $(button);
            const deleteUrl = deleteBtn.data('delete-url');
            const redirectUrl = deleteBtn.data('redirect-url');
            const modalId = deleteBtn.data('modal-id');

            if (!deleteUrl) {
                console.error('DeleteConfirmation: No delete URL specified');
                return;
            }

            const passwordField = $('#deletePassword' + modalId);
            const errorDiv = $('#deleteError' + modalId);
            const spinner = deleteBtn.find('.spinner-border');
            const password = passwordField.val().trim();

            // Client-side validation
            if (!password) {
                errorDiv.text('Please enter your password').show();
                passwordField.focus();
                return;
            }

            // Show loading state
            deleteBtn.prop('disabled', true);
            spinner.show();
            errorDiv.hide();

            // Get CSRF token
            const csrfToken = this._getCSRFToken();
            if (!csrfToken) {
                this._handleError(errorDiv, deleteBtn, spinner, 'CSRF token not found. Please refresh the page.');
                return;
            }

            // Make AJAX DELETE request
            fetch(deleteUrl, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ password: password }),
                credentials: 'same-origin'
            })
            .then(response => {
                // Handle HTTP errors
                if (!response.ok) {
                    return response.json().then(data => {
                        throw {
                            status: response.status,
                            data: data
                        };
                    }).catch(err => {
                        // If JSON parsing fails, throw generic error
                        if (err.status) throw err;
                        throw {
                            status: response.status,
                            data: { message: 'Delete operation failed' }
                        };
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Close modal
                    $('#' + modalId).modal('hide');

                    // Show success message
                    this._showSuccessMessage(data.message || 'Deletion successful');

                    // Redirect after delay
                    const redirectTarget = data.redirect_url || redirectUrl || '/';
                    setTimeout(() => {
                        window.location.href = redirectTarget;
                    }, 1500);
                } else {
                    throw {
                        status: 400,
                        data: data
                    };
                }
            })
            .catch(error => {
                let errorMessage = 'An error occurred during deletion';

                if (error.status) {
                    // Handle specific HTTP status codes
                    switch (error.status) {
                        case 400:
                            errorMessage = error.data.message || error.data.error || 'Invalid request';
                            break;
                        case 401:
                            errorMessage = 'Incorrect password. Please try again.';
                            passwordField.val('').focus();
                            break;
                        case 403:
                            errorMessage = 'You do not have permission to delete this record.';
                            break;
                        case 404:
                            errorMessage = 'Record not found. It may have already been deleted.';
                            break;
                        case 500:
                            errorMessage = 'Server error occurred. Please try again later.';
                            break;
                        default:
                            errorMessage = error.data.message || error.data.error || errorMessage;
                    }
                } else if (error.message) {
                    errorMessage = error.message;
                }

                this._handleError(errorDiv, deleteBtn, spinner, errorMessage);
            });
        },

        /**
         * Get CSRF token from cookie or meta tag
         * @private
         * @returns {string|null} CSRF token value
         */
        _getCSRFToken: function() {
            // First try to get from hidden input
            const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
            if (csrfInput && csrfInput.value) {
                return csrfInput.value;
            }

            // Try meta tag
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            if (csrfMeta && csrfMeta.content) {
                return csrfMeta.content;
            }

            // Try cookie (Django default cookie name)
            const cookies = document.cookie.split(';');
            for (let cookie of cookies) {
                const [name, value] = cookie.trim().split('=');
                if (name === 'csrftoken') {
                    return decodeURIComponent(value);
                }
            }

            return null;
        },

        /**
         * Show success alert message
         * @private
         * @param {string} message - Success message to display
         */
        _showSuccessMessage: function(message) {
            const alertHtml = `
                <div class="alert alert-success alert-dismissible fade show m-3" role="alert" style="position: fixed; top: 60px; right: 20px; z-index: 9999; min-width: 300px;">
                    <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                        <span aria-hidden="true">&times;</span>
                    </button>
                    <i class="fas fa-check-circle"></i> ${this._escapeHtml(message)}
                </div>
            `;

            // Insert at the beginning of body
            document.body.insertAdjacentHTML('afterbegin', alertHtml);

            // Auto-dismiss after 3 seconds
            setTimeout(() => {
                $('.alert-success').fadeOut(400, function() {
                    $(this).remove();
                });
            }, 3000);
        },

        /**
         * Handle error display and state reset
         * @private
         * @param {jQuery} errorDiv - Error message container
         * @param {jQuery} deleteBtn - Delete button element
         * @param {jQuery} spinner - Loading spinner element
         * @param {string} message - Error message to display
         */
        _handleError: function(errorDiv, deleteBtn, spinner, message) {
            errorDiv.html('<i class="fas fa-exclamation-circle"></i> ' + this._escapeHtml(message)).show();
            deleteBtn.prop('disabled', false);
            spinner.hide();
        },

        /**
         * Escape HTML to prevent XSS
         * @private
         * @param {string} text - Text to escape
         * @returns {string} Escaped text
         */
        _escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        /**
         * Initialize event handlers
         */
        init: function() {
            const self = this;

            // Handle delete trigger buttons (show modal) - using event delegation
            $(document).on('click', '.delete-trigger-btn', function(e) {
                e.preventDefault();
                const modalTarget = $(this).data('modal-target');
                if (modalTarget) {
                    self.show(modalTarget);
                } else {
                    console.error('DeleteConfirmation: No modal-target specified on delete trigger button');
                }
            });

            // Handle delete confirm buttons (execute deletion) - using event delegation
            $(document).on('click', '.delete-confirm-btn', function(e) {
                e.preventDefault();
                self.execute(this);
            });

            // Handle Enter key in password fields
            $(document).on('keypress', '[id^="deletePassword"]', function(e) {
                if (e.which === 13) {
                    e.preventDefault();
                    const modalId = this.id.replace('deletePassword', '');
                    $('#confirmDeleteBtn' + modalId).click();
                }
            });

            // Clear error when typing in password field
            $(document).on('input', '[id^="deletePassword"]', function() {
                const modalId = this.id.replace('deletePassword', '');
                $('#deleteError' + modalId).hide();
            });

            // Clear password field when modal is hidden
            // Use class-based selector or simpler ID pattern without case-insensitive flag
            $(document).on('hidden.bs.modal', '.modal[id^="delete"]', function() {
                const modalId = this.id;
                const passwordField = $('#deletePassword' + modalId);
                const errorDiv = $('#deleteError' + modalId);

                if (passwordField.length > 0) {
                    passwordField.val('');
                }
                if (errorDiv.length > 0) {
                    errorDiv.hide().text('');
                }
            });

            console.log('DeleteConfirmation system initialized');
        }
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            window.DeleteConfirmation.init();
        });
    } else {
        window.DeleteConfirmation.init();
    }

})();
