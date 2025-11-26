from django.apps import AppConfig


class PositionsConfig(AppConfig):
    """
    Positions app configuration.
    NO scheduler initialization - handled centrally in config/apps.py
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'positions'
