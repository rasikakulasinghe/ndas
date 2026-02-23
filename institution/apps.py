from django.apps import AppConfig


class InstitutionConfig(AppConfig):
    name = 'institution'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'Institution Management'

    def ready(self):
        pass  # Signal imports will be added in Story 1.3 / Epic 5
