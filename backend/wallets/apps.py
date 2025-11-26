from django.apps import AppConfig


class WalletsConfig(AppConfig):
    """
    Wallets app configuration.
    NO scheduler initialization - handled centrally in config/apps.py
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wallets'
