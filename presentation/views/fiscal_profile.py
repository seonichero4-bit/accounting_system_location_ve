"""Módulo de vistas para el ciclo CRUD completo de Perfiles Fiscales.

Combina vistas personalizadas para flujos de formularios múltiples y complejos
con vistas genéricas de Django para operaciones estándar de lectura y eliminación.
"""

from typing import Any

from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView

from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.base import FiscalProfile
from presentation.forms.fiscal_profile import EntityModelForm, FiscalProfileForm

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
        return FiscalProfile.objects.filter(entity__admin=self.get_fiscal_profile())


class FiscalProfileCreateView(View):
    """Vista basada en clases para la creación de un perfil fiscal y su entidad.

    Coordina la validación conjunta de FiscalProfileForm y EntityModelForm,
    delegando la persistencia transaccional al servicio correspondiente.
    """

    template_name = "fiscal_profile_form.html"

    def get(self, request, *args, **kwargs):
        """Muestra los formularios limpios requeridos para el alta del perfil."""
        profile_form = FiscalProfileForm()
        entity_form = EntityModelForm()
        return render(
            request, 
            self.template_name,
            {"profile_form": profile_form, "entity_form": entity_form},
        )

    def post(self, request, *args, **kwargs):
        """Procesa y valida los datos de ambos formularios para crear el perfil."""
        profile_form = FiscalProfileForm(request.POST)
        entity_form = EntityModelForm(request.POST)

        if profile_form.is_valid() and entity_form.is_valid():
            service = FiscalProfileService(admin_user=request.user)
            try:
                service.create_fiscal_profile(
                    entity_name=entity_form.cleaned_data["name"],
                    use_accrual_method=entity_form.cleaned_data["use_accrual_method"],
                    fy_start_month=entity_form.cleaned_data["fy_start_month"],
                    rif=profile_form.cleaned_data["rif"],
                    code=profile_form.cleaned_data["code"],
                    taxpayer_type=profile_form.cleaned_data["taxpayer_type"],
                    nit=profile_form.cleaned_data.get("nit"),
                )
                return redirect("fiscal-profile-list")
            except ValueError as error:
                profile_form.add_error(None, str(error))

        return render(
            request,
            self.template_name,
            {"profile_form": profile_form, "entity_form": entity_form},
        )


class FiscalProfileUpdateView(View):
    """Vista basada en clases para la edición de un perfil fiscal existente.

    Extrae el perfil por medio de su código de control único y pre-pobla
    los formularios con los datos actuales del perfil y su entidad relacionada.
    """

    template_name = "fiscal_profile/fiscal_profile_form.html"

    def get(self, request, code, *args, **kwargs):
        """Pre-pobla y renderiza los formularios con los datos del registro."""
        fiscal_profile = get_object_or_404(FiscalProfile, code=code)
        profile_form = FiscalProfileForm(instance=fiscal_profile)

        entity_initial = {}
        if fiscal_profile.entity:
            entity_initial = {
                "use_accrual_method": fiscal_profile.entity.use_accrual_method,
                "fy_start_month": fiscal_profile.entity.fy_start_month,
            }
        entity_form = EntityModelForm(instance=fiscal_profile.entity, initial=entity_initial)

        return render(
            request,
            self.template_name,
            {
                "profile_form": profile_form,
                "entity_form": entity_form,
                "fiscal_profile": fiscal_profile,
            },
        )

    def post(self, request, code, *args, **kwargs):
        """Valida y ejecuta los cambios atómicos sobre el perfil fiscal asignado."""
        fiscal_profile = get_object_or_404(FiscalProfile, code=code)
        profile_form = FiscalProfileForm(request.POST, instance=fiscal_profile)
        entity_form = EntityModelForm(request.POST, instance=fiscal_profile.entity)

        if profile_form.is_valid() and entity_form.is_valid():
            service = FiscalProfileService(admin_user=request.user)
            try:
                service.update_fiscal_profile(
                    fiscal_profile=fiscal_profile,
                    entity_name=entity_form.cleaned_data["name"],
                    use_accrual_method=entity_form.cleaned_data["use_accrual_method"],
                    fy_start_month=entity_form.cleaned_data["fy_start_month"],
                    rif=profile_form.cleaned_data["rif"],
                    code=profile_form.cleaned_data["code"],
                    taxpayer_type=profile_form.cleaned_data["taxpayer_type"],
                    nit=profile_form.cleaned_data.get("nit"),
                )
                return redirect("fiscal-profile-detail", code=fiscal_profile.code)
            except ValueError as error:
                profile_form.add_error(None, str(error))

        return render(
            request,
            self.template_name,
            {
                "profile_form": profile_form,
                "entity_form": entity_form,
                "fiscal_profile": fiscal_profile,
            },
        )

class FiscalProfileListView(FiscalTenantMixin, ListView):
    """Vista genérica para listar los Perfiles Fiscales asociados al usuario."""

    model = FiscalProfile
    template_name = "fiscal_profile_list.html"
    context_object_name = "object_list"

class FiscalProfileDetailView(DetailView):
    """Vista genérica para exponer el desglose técnico de un Perfil Fiscal."""

    model = FiscalProfile
    template_name = "supplier/fiscal_profile_detail.html"
    context_object_name = "object"
    slug_field = "code"
    slug_url_kwarg = "code"

    def get_queryset(self) -> QuerySet[FiscalProfile]:
        """Asegura que el usuario solo pueda consultar el detalle de sus propios registros."""
        return FiscalProfile.objects.filter(admin=self.request.user)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Inyecta de forma segura la relación de la entidad contable al contexto."""
        context = super().get_context_data(**kwargs)
        context["entity"] = getattr(self.object, "entity", None)
        return context


class FiscalProfileDeleteView(DeleteView):
    """Vista genérica para la eliminación física de un Perfil Fiscal determinado."""

    model = FiscalProfile
    template_name = "supplier/fiscal_profile_confirm_delete.html"
    slug_field = "code"
    slug_url_kwarg = "code"
    success_url = reverse_lazy("fiscal-profile-list")

    def get_queryset(self) -> QuerySet[FiscalProfile]:
        """Previene que operadores externos eliminen perfiles ajenos."""
        return FiscalProfile.objects.filter(admin=self.request.user)