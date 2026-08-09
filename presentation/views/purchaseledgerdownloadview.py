from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

# Asumiendo las importaciones correspondientes
from business_logic.services.purchaseledgerexcelbuilderservice import PurchaseLedgerExcelBuilder
from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.base import FiscalProfile
from presentation.mixins.requestscopedquerysetmixin import RequestScopedQuerySetMixin

class PurchaseLedgerDownloadView(LoginRequiredMixin, RequestScopedQuerySetMixin, View):
    """
    Vista responsable de detonar la descarga del Libro de Compras en formato XLSX.
    Aplica el mixin de aislamiento para inyectar los filtros for_request de manera segura.
    """
    model = PurchaseLedgerInvoice
    
    def get(self, request, *args, **kwargs):
        # 1. Recuperar dependencias operativas inyectadas en el request o la URL
        profile_pk = self.kwargs.get('profile_pk')
        fiscal_profile = get_object_or_404(FiscalProfile, pk=profile_pk)
        
        # Validación de seguridad explícita 
        if fiscal_profile.entity.admin != request.user:
            raise PermissionDenied("El usuario no tiene acceso a la contabilidad de este inquilino.")
            
        fiscal_period = request.fiscal_period # Inyectado previamente por middleware/contexto
        
        if not fiscal_period:
            raise ValueError("El período fiscal no fue determinado en el contexto de la solicitud.")

        # 2. Extraer QuerySet acotado, ejecutando for_request(request) gracias al mixin[cite: 2]
        # Filtra adicionalmente los documentos que correspondan al período de aplicación solicitado
        period_str = fiscal_period.strftime("%m-%Y")
        queryset = self.get_queryset().filter(application_month_year=period_str).order_date('date')

        # 3. Delegar carga computacional a la capa de servicios y retornar stream binario
        builder = PurchaseLedgerExcelBuilder(
            fiscal_profile=fiscal_profile,
            fiscal_period=fiscal_period,
            queryset=queryset
        )
        
        return builder.build().get_response()