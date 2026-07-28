from django.views.generic import FormView
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.core.exceptions import ValidationError

from presentation.mixins import FiscalTenantMixin
from business_logic.services.fiscalbatchprocessingservice import FiscalBatchProcessingService

class ProcessFiscalBatchView(FiscalTenantMixin, FormView):
    """Vista para ejecutar el procesamiento en lote del Libro de Compras."""
    
    template_name = "purchase_book.html"
    success_url = reverse_lazy("purchase-invoice-list")

    def form_valid(self, form):
        fiscal_profile = self.get_fiscal_profile()
        period = form.cleaned_data["application_month_year"]

        service = FiscalBatchProcessingService(
            fiscal_profile=fiscal_profile,
            application_month_year=period,
        )

        try:
            asiento_1, asiento_2 = service.execute_batch_processing()
            msg = f"Lote {period} procesado con éxito. Asiento Compras: {asiento_1.je_number}."
            if asiento_2:
                msg += f" Asiento Retenciones IVA: {asiento_2.je_number}."
            messages.success(self.request, msg)

        except ValidationError as ve:
            messages.error(self.request, f"Error de validación: {ve.message}")
        except Exception as e:
            messages.error(self.request, f"Error inesperado al procesar el lote: {str(e)}")

        return redirect(self.success_url)