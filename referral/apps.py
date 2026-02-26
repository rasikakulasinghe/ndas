from django.apps import AppConfig


class ReferralConfig(AppConfig):
    name = 'referral'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'Referral System'

    def ready(self):
        # Story 5.1: Signal registration
        # import referral.signals  # Uncomment when Story 5.1 is implemented
        pass
