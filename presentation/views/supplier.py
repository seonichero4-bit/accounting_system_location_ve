"""Módulo de vistas CRUD para la gestión de proveedores locales."""

from typing import Any
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import FormView, ListView, DetailView, CreateView, UpdateView, DeleteView

from accounting_system_ve.data_access.models.supplier import ProveedorLocal
from accounting_system_ve.data_access.models.base import FiscalProfile
from ..forms.supplier import ProveedorLocalForm
from accounting_system_ve.business_logic.servicios.proveedor_servicio import ProveedorService


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
        return ProveedorLocal.objects.filter(fiscal_profile=self.get_fiscal_profile())


class ProveedorLocalListView(FiscalTenantMixin, ListView):
    """Vista para listar los proveedores del inquilino activo."""
    model = ProveedorLocal
    context_object_name = "proveedores"

class ProveedorLocalDetailView(FiscalTenantMixin, DetailView):
    """Vista para ver el detalle de un proveedor específico."""
    model = ProveedorLocal
    context_object_name = "proveedor"


class ProveedorLocalCreateView(FiscalTenantMixin, FormView):
    """Vista para la creación o recuperación de un proveedor local.

    Utiliza FormView para separar estrictamente la lógica de negocio de la
    capa de presentación, delegando el procesamiento al servicio del dominio.
    """
    form_class = ProveedorLocalForm
    template_name = "fiscal_localization/proveedorlocal_form.html"

    def form_valid(self, form: ProveedorLocalForm) -> HttpResponse:
        """Procesa el formulario validado utilizando la capa de servicios.

        Instancia el servicio con el contexto del inquilino, delega la decisión 
        transaccional (crear o recuperar), y gestiona únicamente la redirección.

        Args:
            form (ProveedorLocalForm): El formulario con los datos validados.

        Returns:
            HttpResponse: Redirección a la vista de detalle del proveedor procesado.
        """
       
        servicio = ProveedorService(fiscal_profile=self.get_fiscal_profile())
    
        proveedor, creado = servicio.registrar_o_recuperar_local(form.cleaned_data)
        
        return redirect("proveedor-detail", pk=proveedor.pk)


class ProveedorLocalUpdateView(FiscalTenantMixin, UpdateView):
    """Vista para la actualización de datos de un proveedor."""
    model = ProveedorLocal
    form_class = ProveedorLocalForm

    def get_success_url(self) -> str:
        return reverse("proveedor-detail", kwargs={"pk": self.object.pk})


class ProveedorLocalDeleteView(FiscalTenantMixin, DeleteView):
    """Vista para eliminar lógicamente o físicamente un proveedor."""
    model = ProveedorLocal
    success_url = reverse_lazy("proveedor-list")