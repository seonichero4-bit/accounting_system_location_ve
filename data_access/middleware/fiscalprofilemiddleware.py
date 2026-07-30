from django.utils.functional import SimpleLazyObject
from data_access.models.base import FiscalProfile

def get_fiscal_profile(request) -> FiscalProfile | None:
    if not hasattr(request, '_cached_fiscal_profile'):
        profile = None
        if request.user.is_authenticated:
            profile_id = request.session.get('active_fiscal_profile_id')
            if profile_id:
                try:
                    # Garantiza que el perfil extraído siga perteneciendo al usuario autenticado
                    profile = FiscalProfile.objects.select_related('entity').get(
                        pk=profile_id,
                        entity__admin=request.user
                    )
                except FiscalProfile.DoesNotExist:
                    # Si el ID guardado no existe o revocaron accesos, invalida la clave de sesión
                    request.session.pop('active_fiscal_profile_id', None)
        
        request._cached_fiscal_profile = profile
    return request._cached_fiscal_profile


class FiscalProfileMiddleware:
    """Middleware para inyectar `request.fiscal_profile` en cada petición HTTP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Asigna la evaluación lazy al atributo de la petición
        request.fiscal_profile = SimpleLazyObject(lambda: get_fiscal_profile(request))
        
        response = self.get_response(request)
        return response