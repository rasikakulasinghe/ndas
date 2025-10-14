/**
 * NDAS Patient Deletion Handler
 * Manages secure patient deletion with password confirmation
 */

(function() {
    'use strict';

    window.PatientDeletion = {
        /**
         * Show patient deletion confirmation modal
         */
        confirm: function() {
            const modal = $('#deletePatientModal');
            modal.modal('show');
            $('#deletePassword').val('');
            $('#deleteError').hide();
        },

        /**
         * Execute patient deletion after password verification
         * @param {string} patientId - Patient ID to delete
         * @param {string} deleteUrl - Delete endpoint URL
         */
        execute: function(patientId, deleteUrl) {
            const password = $('#deletePassword').val();
            const deleteBtn = $('#confirmDeleteBtn');
            const spinner = $('#deleteSpinner');
            const errorDiv = $('#deleteError');

            if (!password) {
                errorDiv.text('Please enter your password').show();
                return;
            }

            deleteBtn.prop('disabled', true);
            spinner.show();
            errorDiv.hide();

            fetch(deleteUrl, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ password: password })
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.message || data.error || 'Delete operation failed');
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    $('#deletePatientModal').modal('hide');

                    // Show success message
                    document.body.insertAdjacentHTML('afterbegin',
                        `<div class="alert alert-success alert-dismissible m-3">
                            <button type="button" class="close" data-dismiss="alert">&times;</button>
                            <i class="fas fa-check-circle"></i> ${data.message}
                        </div>`
                    );

                    // Redirect after delay
                    setTimeout(() => {
                        window.location.href = data.redirect_url || '/manager/patient/';
                    }, 1500);
                } else {
                    throw new Error(data.message || 'Delete operation failed');
                }
            })
            .catch(error => {
                let errorMessage = error.message || 'An error occurred while deleting the patient.';
                errorDiv.text(errorMessage).show();
            })
            .finally(() => {
                deleteBtn.prop('disabled', false);
                spinner.hide();
            });
        },

        /**
         * Initialize patient deletion handlers
         */
        init: function() {
            // Handle Enter key in password field
            $(document).on('keypress', '#deletePassword', function(e) {
                if (e.which === 13) {
                    const patientId = $('#deletePatientModal').data('patient-id');
                    const deleteUrl = $('#deletePatientModal').data('delete-url');
                    if (patientId && deleteUrl) {
                        PatientDeletion.execute(patientId, deleteUrl);
                    }
                }
            });
        }
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => PatientDeletion.init());
    } else {
        PatientDeletion.init();
    }

})();
