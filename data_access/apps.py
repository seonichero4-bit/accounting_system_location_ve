from django.apps import AppConfig

class DataAccessConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'data_access'  # Este debe coincidir exactamente con el nombre de la carpeta
    verbose_name = 'Acceso a Datos'