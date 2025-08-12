from django.apps import AppConfig


class FormConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'form'
    verbose_name = 'Gestion des Interventions'

    def ready(self):
        """Import signals when the app is ready"""
        import form.signals