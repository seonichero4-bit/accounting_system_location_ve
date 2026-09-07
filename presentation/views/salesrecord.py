"""Módulo de vistas basadas en clases para el CRUD de SalesRecord."""

from typing import Any, Dict

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, DeleteView, DetailView, ListView

from data_access.models.sales_record import SalesRecord
from presentation.mixins.requestscopedquerysetmixin import RequestScopedQuerySetMixin
from presentation.mixins.fiscalformkwargsmixin import FiscalFormKwargsMixin 
from presentation.forms.salesrecord import SalesRecordForm

class SalesRecordListView(RequestScopedQuerySetMixin, ListView):
    """Vista para listar los registros de ventas del inquilino actual."""

    model = SalesRecord
    template_name = 'sales_record_list.html'
    context_object_name = 'sales_records'

class SalesRecordDetailView(RequestScopedQuerySetMixin, DetailView):
    """Vista para visualizar el detalle de un registro de venta específico."""

    model = SalesRecord
    template_name = 'sales_record_detail.html'
    context_object_name = 'sales_record'

class SalesRecordDeleteView(RequestScopedQuerySetMixin, DeleteView):
    """Vista para eliminar un registro de venta.
    
    Asegura que un inquilino solo pueda eliminar sus propios registros.
    """

    model = SalesRecord
    template_name = 'sales_record_confirm_delete.html'
    success_url = reverse_lazy('sales_record_list')

class SalesRecordCreateView(RequestScopedQuerySetMixin, FiscalFormKwargsMixin, CreateView):
    """Vista acotada para crear un nuevo registro en el Libro de Ventas."""
    template_name = 'sales_record_form.html'
    model = SalesRecord
    form_class = SalesRecordForm
    success_url =  '/'
    
class SalesRecordUpdateView(RequestScopedQuerySetMixin, UpdateView):
    """Vista acotada para editar un registro existente en el Libro de Ventas."""
    template_name = 'sales_record_form.html'
    model = SalesRecord
    form_class = SalesRecordForm
    success_url = '/'