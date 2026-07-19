
from data_access.models.base import FiscalProfile


class FiscalTenantMixin:
    """Mixin base para inyectar y aislar el perfil fiscal activo en las vistas."""

    def get_fiscal_profile(self) -> FiscalProfile:
        """Obtiene el perfil fiscal del inquilino actual.
        
        Nota: En producción, esto debe derivarse de `self.request.user.entity.fiscal_profile`
        o del middleware activo. Por simplicidad del CRUD, retorna el primero disponible.
        """
        return FiscalProfile.objects.first()

    def get_queryset(self):
        """Aísla las consultas estrictamente al perfil fiscal actual."""
        current_fiscalprofile = self.get_fiscal_profile()

        if current_fiscalprofile is None:
            return FiscalProfile.objects.none()

        return FiscalProfile.objects.filter(pk=current_fiscalprofile.pk)