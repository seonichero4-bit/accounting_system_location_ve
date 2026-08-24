"""Módulo de vistas basadas en clases para el ciclo CRUD del Libro de Compras.

Utiliza las vistas genéricas de Django para procesar la creación, lectura,
actualización y eliminación de registros del modelo PurchaseLedgerInvoice,
garantizando el aislamiento multi-inquilino a través del usuario autenticado[cite: 1].
"""

from typing import Any

from django.db.models.query import QuerySet
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)

from utils import unwrap_lazy_object
from data_access.models.purchase_book import PurchaseLedgerInvoice
from presentation.forms.purchase_book import PurchaseLedgerInvoiceForm
from data_access.models.base import FiscalProfile
from presentation.mixins.requestscopedquerysetmixin import RequestScopedQuerySetMixin

class PurchaseLedgerInvoiceListView(RequestScopedQuerySetMixin, ListView):
    """Vista genérica para listar las facturas del Libro de Compras[cite: 1]."""

    model = PurchaseLedgerInvoice
    template_name = "invoice_list.html"
    context_object_name = "invoices"


class PurchaseLedgerInvoiceDetailView(RequestScopedQuerySetMixin, DetailView):
    """Vista genérica para exponer el desglose técnico de una factura específica[cite: 1]."""

    model = PurchaseLedgerInvoice
    template_name = "invoice_detail.html"
    context_object_name = "invoice"


class PurchaseLedgerInvoiceCreateView(RequestScopedQuerySetMixin, CreateView):
    """Vista genérica para el alta y procesamiento de nuevas facturas fiscales[cite: 1]."""

    model = PurchaseLedgerInvoice
    form_class = PurchaseLedgerInvoiceForm
    template_name = "invoice_form.html"
    success_url = reverse_lazy("purchase-invoice-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        
        fiscal_profile_obj = unwrap_lazy_object(getattr(self.request, "fiscal_profile", None))
        
        # Los enviamos como kwargs adicionales al formulario
        kwargs['fiscal_profile'] = fiscal_profile_obj
        return kwargs

    def get_form(self, form_class=None):
        """Inyecta de forma temprana el perfil fiscal activo en la instancia del formulario[cite: 1]."""
        form = super().get_form(form_class)

        #Extraemos el datetime.date real envuelto en el SimpleLazyObject

        fiscal_period_date = unwrap_lazy_object(getattr(self.request, "fiscal_period", None))
        fiscal_profile_obj = unwrap_lazy_object(getattr(self.request, "fiscal_profile", None))  

        form.instance.fiscal_profile = fiscal_profile_obj
        form.instance.fiscal_period = fiscal_period_date
        return form

    def form_valid(self, form):
        """Intercepta las excepciones del modelo o la BD al intentar guardar."""
        try:
            with transaction.atomic():
                return super().form_valid(form)
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)
        except IntegrityError as e:
            form.add_error(None, f"Error de integridad en la base de datos (Restricción violada): {e}")
            return self.form_invalid(form)


class PurchaseLedgerInvoiceUpdateView(RequestScopedQuerySetMixin, UpdateView):
    """Vista genérica para la edición de parámetros de una factura existente[cite: 1]."""

    model = PurchaseLedgerInvoice
    form_class = PurchaseLedgerInvoiceForm
    template_name = "invoice_form.html"
    success_url = reverse_lazy("purchase-invoice-list")

    def form_valid(self, form):
        """Intercepta excepciones que bloquean la modificación (e.g. estado PROCESSED)[cite: 3]."""
        try:
            return super().form_valid(form)
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)
        except IntegrityError as e:
            form.add_error(None, f"Error de integridad en la base de datos: {e}")
            return self.form_invalid(form)


class PurchaseLedgerInvoiceDeleteView(RequestScopedQuerySetMixin, DeleteView):
    """Vista genérica para la remoción o anulación física de una factura[cite: 1]."""

    model = PurchaseLedgerInvoice
    template_name = "invoice_confirm_delete.html"
    success_url = reverse_lazy("purchase-invoice-list")

    def form_valid(self, form):
        """Intercepta excepciones lanzadas por el método delete() del modelo[cite: 3]."""
        try:
            return super().form_valid(form)
        except ValidationError as e:
            # En Django >4.0 DeleteView utiliza FormMixin, permitiendo manejar errores en el form
            form.add_error(None, e)
            return self.form_invalid(form)
        except IntegrityError as e:
            form.add_error(None, f"No se puede eliminar el registro por integridad referencial: {e}")
            return self.form_invalid(form)