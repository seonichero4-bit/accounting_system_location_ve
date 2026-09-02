"""Vistas basadas en clases para el CRUD completo del modelo Customer.

Implementa las operaciones de listado, detalle, creación, actualización y 
eliminación de clientes, garantizando el aislamiento multi-inquilino y la 
correcta captura de excepciones a nivel de base de datos y validaciones de negocio.
"""

from typing import Any, Dict

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView
)

from data_access.models.customer import Customer
from presentation.forms.customer import CustomerForm
from presentation.mixins.requestscopedquerysetmixin import RequestScopedQuerySetMixin
from utils import unwrap_lazy_object


class CustomerListView(RequestScopedQuerySetMixin, ListView):
    """Vista para listar los clientes asociados al inquilino actual."""
    
    model = Customer
    template_name = 'customer_list.html'
    context_object_name = 'customer_list'
    paginate_by = 20


class CustomerDetailView(RequestScopedQuerySetMixin, DetailView):
    """Vista para visualizar los detalles de un cliente específico."""
    
    model = Customer
    template_name = 'customer_detail.html'
    context_object_name = 'customer'


class CustomerCreateView(RequestScopedQuerySetMixin, CreateView):
    """Vista para la creación de un nuevo cliente."""
    
    model = Customer
    form_class = CustomerForm
    template_name = 'customer_form.html'
    success_url = reverse_lazy('customer_list')

    def get_form_kwargs(self) -> Dict[str, Any]:
        """Inyecta el perfil fiscal del usuario en el formulario."""
        kwargs = super().get_form_kwargs()
        kwargs['fiscal_profile'] = unwrap_lazy_object(getattr(self.request, 'fiscal_profile', None))
        return kwargs

    def form_valid(self, form: CustomerForm) -> HttpResponse:
        """Guarda el formulario capturando errores de validación de BD o Modelo."""
        try:
            return super().form_valid(form)
        except (ValidationError, IntegrityError) as e:
            if isinstance(e, ValidationError):
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            form.add_error(field, error)
                else:
                    form.add_error(None, e)
            else:
                form.add_error(None, "Error de integridad: Restricción de base de datos violada.")
            return self.form_invalid(form)


class CustomerUpdateView(RequestScopedQuerySetMixin, UpdateView):
    """Vista para la actualización de un cliente existente."""
    
    model = Customer
    form_class = CustomerForm
    template_name = 'customer_form.html'
    success_url = reverse_lazy('customer_list')

    def get_form_kwargs(self) -> Dict[str, Any]:
        """Inyecta el perfil fiscal del usuario en el formulario."""
        kwargs = super().get_form_kwargs()
        kwargs['fiscal_profile'] = unwrap_lazy_object(getattr(self.request, 'fiscal_profile', None))
        return kwargs

    def form_valid(self, form: CustomerForm) -> HttpResponse:
        """Guarda el formulario capturando errores de validación de BD o Modelo."""
        try:
            return super().form_valid(form)
        except (ValidationError, IntegrityError) as e:
            if isinstance(e, ValidationError):
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            form.add_error(field, error)
                    else:
                        form.add_error(None, e)
            else:
                form.add_error(None, "Error de integridad: Restricción de base de datos violada.")
            return self.form_invalid(form)


class CustomerDeleteView(RequestScopedQuerySetMixin, DeleteView):
    """Vista para la eliminación de un cliente existente."""
    
    model = Customer
    template_name = 'customer_confirm_delete.html'
    success_url = reverse_lazy('customer_list')