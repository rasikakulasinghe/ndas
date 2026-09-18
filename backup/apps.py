from django.apps import AppConfig


class BackupConfig(AppConfig):
    name = 'backup'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'Backup & Restore'
