"""Módulo de vistas CRUD para la gestión de proveedores locales."""

from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import FormView, ListView, DetailView, CreateView, UpdateView, DeleteView

from data_access.models.supplier import LocalSupplier
from data_access.models.base import FiscalProfile
from ..forms.supplier import LocalSupplierForm
from business_logic.services.supplier_service import SupplierService
from presentation.mixins.requestscopedquerysetmixin import RequestScopedQuerySetMixin

class LocalSupplierListView(RequestScopedQuerySetMixin, ListView):
    """Vista para listar los proveedores del inquilino activo."""
    model = LocalSupplier
    context_object_name = "suppliers"
    template_name = "localsupplier_list.html"


class LocalSupplierDetailView(RequestScopedQuerySetMixin, DetailView):
    """Vista para ver el detalle de un proveedor específico."""
    model = LocalSupplier
    context_object_name = "supplier"
    template_name = "localsupplier_detail.html"

class LocalSupplierCreateView(RequestScopedQuerySetMixin, FormView):
    """Vista para la creación o recuperación de un proveedor local.

    Utiliza FormView para separar estrictamente la lógica de negocio de la
    capa de presentación, delegando el procesamiento al servicio del dominio.
    """
    model = LocalSupplier
    form_class = LocalSupplierForm 
    template_name = "localsupplier_form.html"

    def form_valid(self, form: LocalSupplierForm) -> HttpResponse:
        """Procesa el formulario validado utilizando la capa de servicios.

        Instancia el servicio con el contexto del inquilino, delega la decisión 
        transaccional (crear o recuperar), y gestiona únicamente la redirección.

        Args:
            form (ProveedorLocalForm): El formulario con los datos validados.

        Returns:
            HttpResponse: Redirección a la vista de detalle del proveedor procesado.
        """
        
        service = SupplierService(fiscal_profile=self.request.user)
    
        supplier, created = service.register_or_retrieve_local(form.cleaned_data)
        
        return redirect("supplier-detail", pk=supplier.pk)


class LocalSupplierUpdateView(RequestScopedQuerySetMixin, UpdateView):
    """Vista para la actualización de datos de un proveedor."""
    model = LocalSupplier
    form_class = LocalSupplierForm
    template_name = "localsupplier_form.html"

    def get_success_url(self) -> str:
        return reverse("supplier-detail", kwargs={"pk": self.object.pk})


class LocalSupplierDeleteView(RequestScopedQuerySetMixin, DeleteView):
    """Vista para eliminar lógicamente o físicamente un proveedor."""
    model = LocalSupplier
    template_name = "localsupplier_confirm_delete.html"
    success_url = reverse_lazy("supplier-list")
    