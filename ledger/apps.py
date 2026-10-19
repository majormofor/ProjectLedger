from django.apps import AppConfig

class LedgerConfig(AppConfig):
    name = 'ledger'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from . import notifications  # Register audit-event email notifications.
