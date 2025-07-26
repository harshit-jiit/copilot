from django.apps import AppConfig


class GymOwnersonfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gymowners'

    def ready(self):
        import gymowners.signals
