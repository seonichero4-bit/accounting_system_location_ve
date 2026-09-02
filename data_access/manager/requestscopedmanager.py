from django.db import models

from utils import unwrap_lazy_object

class RequestScopedQuerySet(models.QuerySet):
    def for_request(self, request):
        """
        Aplica los filtros basados en la información del request
        (tenant, fiscal_profile, fiscal_period y admin de entity).
        """
        if not request.user.is_authenticated:
            return self.none()

        # 1. Si el modelo posee 'fiscal_period' (filtra por profile y period)
        if hasattr(self.model, 'fiscal_period'):
            req_fiscal_period = unwrap_lazy_object(getattr(request, "fiscal_period", None))
            req_fiscal_profile = unwrap_lazy_object(getattr(request, "fiscal_profile", None))
            filters = {}
            if req_fiscal_profile:
                filters['fiscal_profile'] = req_fiscal_profile
            if req_fiscal_period:
                filters['fiscal_period'] = req_fiscal_period
            
            qs = self.filter(**filters)

        # 2. Si el modelo posee 'fiscal_profile' pero NO 'fiscal_period'
        elif hasattr(self.model, 'fiscal_profile'):
            req_fiscal_profile = unwrap_lazy_object(getattr(request, "fiscal_profile", None))
            if req_fiscal_profile:
                qs = self.filter(fiscal_profile=req_fiscal_profile)

        # 3. Caso para el modelo 'FiscalProfile' (sin los atributos anteriores)
        elif self.model.__name__ == 'FiscalProfile':
            qs = self.filter(entity__admin=request.user)

        return qs

class RequestScopedManager(models.Manager.from_queryset(RequestScopedQuerySet)):
    pass