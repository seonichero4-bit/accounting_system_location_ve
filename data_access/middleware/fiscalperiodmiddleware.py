from django.utils.functional import SimpleLazyObject
from data_access.models.fiscalperiod import FiscalPeriod

def get_fiscal_period(request) -> FiscalPeriod | None:
    if not hasattr(request, '_cached_fiscal_period'):
        period = None
        if request.user.is_authenticated:
            # Obtiene el perfil fiscal activo garantizando aislamiento por inquilino
            profile = getattr(request, 'fiscal_profile', None)
            period_id = request.session.get('active_fiscal_period_id')
            
            if profile and period_id:
                try:
                    period = FiscalPeriod.objects.get(pk=period_id)
                except FiscalPeriod.DoesNotExist:
                    request.session.pop('active_fiscal_period_id', None)

        # Validación del valor del periodo fiscal antes de retornar
        if period:
            if period.subsequent_period:
                selected_period_value = period.subsequent_period
            else:
                selected_period_value = period.start_period

        request._cached_fiscal_period = selected_period_value

    return request._cached_fiscal_period


class FiscalPeriodMiddleware:
    """Middleware para inyectar  y `request.fiscal_period` en cada petición."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.fiscal_period = SimpleLazyObject(lambda: get_fiscal_period(request))
        
        response = self.get_response(request)
        return response