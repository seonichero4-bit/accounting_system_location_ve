from utils import unwrap_lazy_object

class FiscalFormKwargsMixin:
    """Inyecta el contexto fiscal actual en los formularios de las vistas de creación."""
    def get_form_kwargs(self) -> dict:
        kwargs = super().get_form_kwargs()
        
        if hasattr(self.request, 'fiscal_profile'):
            kwargs['fiscal_profile'] = unwrap_lazy_object(self.request.fiscal_profile)
        if hasattr(self.request, 'fiscal_period'):
            kwargs['fiscal_period'] = unwrap_lazy_object(self.request.fiscal_period)
            
        return kwargs