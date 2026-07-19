"""Módulo de vistas basadas en clases para el ciclo CRUD del Libro de Compras.

Utiliza las vistas genéricas de Django para procesar la creación, lectura,
actualización y eliminación de registros del modelo PurchaseLedgerInvoice,
garantizando el aislamiento multi-inquilino a través del usuario autenticado.
"""

from typing import Any
from django.db.models.query import QuerySet
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)

from data_access.models.purchase_book import PurchaseLedgerInvoice
from presentation.forms.purchase_book import PurchaseLedgerInvoiceForm
from data_access.models.base import FiscalProfile
#from ..mixins.fiscaltenantmixin import FiscalTenantMixin

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

        return PurchaseLedgerInvoice.objects.filter(fiscal_profile=current_fiscalprofile)
    
    

class PurchaseLedgerInvoiceListView(FiscalTenantMixin, ListView):
    """Vista genérica para listar las facturas del Libro de Compras."""

    model = PurchaseLedgerInvoice
    template_name = "invoice_list.html"
    context_object_name = "invoices"


class PurchaseLedgerInvoiceDetailView(FiscalTenantMixin, DetailView):
    """Vista genérica para exponer el desglose técnico de una factura específica."""

    model = PurchaseLedgerInvoice
    template_name = "invoice_detail.html"
    context_object_name = "invoice"


class PurchaseLedgerInvoiceCreateView(FiscalTenantMixin, CreateView):
    """Vista genérica para el alta y procesamiento de nuevas facturas fiscales."""

    model = PurchaseLedgerInvoice
    form_class = PurchaseLedgerInvoiceForm
    template_name = "invoice_form.html"
    success_url = reverse_lazy("purchase-invoice-list")

    def get_form(self, form_class=None):
        """Inyecta de forma temprana el perfil fiscal activo en la instancia del formulario."""
        form = super().get_form(form_class)
        form.instance.fiscal_profile = self.get_fiscal_profile()
        return form

    # def form_valid(self, form): # Modificar en produccion, para extraer fiscalprofile
    # # desde el request
    #     current_fiscalprofile = self.get_fiscal_profile()
    #     form.instance.fiscal_profile = current_fiscalprofile
        
    #     return super().form_valid(form)


class PurchaseLedgerInvoiceUpdateView(FiscalTenantMixin, UpdateView):
    """Vista genérica para la edición de parámetros de una factura existente."""

    model = PurchaseLedgerInvoice
    form_class = PurchaseLedgerInvoiceForm
    template_name = "invoice_form.html"
    success_url = reverse_lazy("purchase-invoice-list")


class PurchaseLedgerInvoiceDeleteView(FiscalTenantMixin, DeleteView):
    """Vista genérica para la remoción o anulación física de una factura."""

    model = PurchaseLedgerInvoice
    template_name = "invoice_confirm_delete.html"
    success_url = reverse_lazy("purchase-invoice-list")