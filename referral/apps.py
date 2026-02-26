from django.apps import AppConfig


class ReferralConfig(AppConfig):
    name = 'referral'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'Referral System'

    def ready(self):
        import referral.signals  # noqa: F401 — registers all signal handlers
