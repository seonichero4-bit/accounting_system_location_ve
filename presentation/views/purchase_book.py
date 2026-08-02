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
from presentation.mixins.requestscopedquerysetmixin import RequestScopedQuerySetMixin

class PurchaseLedgerInvoiceListView(RequestScopedQuerySetMixin, ListView):
    """Vista genérica para listar las facturas del Libro de Compras."""

    model = PurchaseLedgerInvoice
    template_name = "invoice_list.html"
    context_object_name = "invoices"


class PurchaseLedgerInvoiceDetailView(RequestScopedQuerySetMixin, DetailView):
    """Vista genérica para exponer el desglose técnico de una factura específica."""

    model = PurchaseLedgerInvoice
    template_name = "invoice_detail.html"
    context_object_name = "invoice"


class PurchaseLedgerInvoiceCreateView(RequestScopedQuerySetMixin, CreateView):
    """Vista genérica para el alta y procesamiento de nuevas facturas fiscales."""

    model = PurchaseLedgerInvoice
    form_class = PurchaseLedgerInvoiceForm
    template_name = "invoice_form.html"
    success_url = reverse_lazy("purchase-invoice-list")

    def get_form(self, form_class=None):
        """Inyecta de forma temprana el perfil fiscal activo en la instancia del formulario."""
        form = super().get_form(form_class)
        form.instance.fiscal_profile = self.request.fiscal_profile
        form.instance.fiscal_period = self.request.fiscal_period
        return form

class PurchaseLedgerInvoiceUpdateView(RequestScopedQuerySetMixin, UpdateView):
    """Vista genérica para la edición de parámetros de una factura existente."""

    model = PurchaseLedgerInvoice
    form_class = PurchaseLedgerInvoiceForm
    template_name = "invoice_form.html"
    success_url = reverse_lazy("purchase-invoice-list")


class PurchaseLedgerInvoiceDeleteView(RequestScopedQuerySetMixin, DeleteView):
    """Vista genérica para la remoción o anulación física de una factura."""

    model = PurchaseLedgerInvoice
    template_name = "invoice_confirm_delete.html"
    success_url = reverse_lazy("purchase-invoice-list")