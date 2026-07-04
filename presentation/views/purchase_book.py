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
from ..mixins.fiscaltenantmixin import FiscalTenantMixin

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