"""Módulo de vistas para el ciclo CRUD completo de Perfiles Fiscales.

Combina vistas personalizadas para flujos de formularios múltiples y complejos
con vistas genéricas de Django para operaciones estándar de lectura y eliminación.
"""

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView

from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.base import FiscalProfile
from presentation.forms.fiscal_profile import EntityModelForm, FiscalProfileForm


class FiscalProfileCreateView(View):
    """Vista para coordinar la creación atómica de un Perfil Fiscal y su Entidad."""

    template_name = "fiscal_profile_form.html"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Renderiza los formularios de creación con sus prefijos únicos."""
        context = {
            "profile_form": FiscalProfileForm(prefix="profile"),
            "entity_form": EntityModelForm(prefix="entity"),
            "is_update": False,
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Valida y procesa la creación a través de la capa de servicios."""
        profile_form = FiscalProfileForm(request.POST, prefix="profile")
        entity_form = EntityModelForm(request.POST, prefix="entity")

        if profile_form.is_valid() and entity_form.is_valid():
            service = FiscalProfileService(admin_user=request.user)
            try:
                p_data = profile_form.cleaned_data
                e_data = entity_form.cleaned_data

                service.create_fiscal_profile(
                    entity_name=e_data["name"],
                    rif=p_data["rif"],
                    code=p_data["code"],
                    taxpayer_type=p_data["taxpayer_type"],
                    nit=p_data.get("nit"),
                    use_accrual_method=e_data.get("use_accrual_method", True),
                    fy_start_month=e_data.get("fy_start_month", 1),
                )
                return redirect("fiscal-profile-list")
            except ValueError as error:
                profile_form.add_error(None, str(error))

        context = {
            "profile_form": profile_form,
            "entity_form": entity_form,
            "is_update": False,
        }
        return render(request, self.template_name, context)


class FiscalProfileUpdateView(LoginRequiredMixin, View):
    """Vista para coordinar la edición atómica de un Perfil Fiscal y su Entidad."""

    template_name = "supplier/fiscal_profile_form.html"

    def get(self, request: HttpRequest, code: str, *args: Any, **kwargs: Any) -> HttpResponse:
        """Carga los datos existentes aislando por el usuario operador."""
        fiscal_profile = get_object_or_404(FiscalProfile, code=code, admin=request.user)
        entity = getattr(fiscal_profile, "entity", None)

        context = {
            "profile_form": FiscalProfileForm(instance=fiscal_profile, prefix="profile"),
            "entity_form": EntityModelForm(instance=entity, prefix="entity"),
            "object": fiscal_profile,
            "is_update": True,
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest, code: str, *args: Any, **kwargs: Any) -> HttpResponse:
        """Procesa y guarda los cambios de la edición de manera transaccional."""
        fiscal_profile = get_object_or_404(FiscalProfile, code=code, admin=request.user)
        entity = getattr(fiscal_profile, "entity", None)

        profile_form = FiscalProfileForm(request.POST, instance=fiscal_profile, prefix="profile")
        entity_form = EntityModelForm(request.POST, instance=entity, prefix="entity")

        if profile_form.is_valid() and entity_form.is_valid():
            service = FiscalProfileService(admin_user=request.user)
            try:
                service.update_fiscal_profile(
                    fiscal_profile=fiscal_profile,
                    entity=entity,
                    profile_data=profile_form.cleaned_data,
                    entity_data=entity_form.cleaned_data,
                )
                return redirect("fiscal-profile-list")
            except ValueError as error:
                profile_form.add_error(None, str(error))

        context = {
            "profile_form": profile_form,
            "entity_form": entity_form,
            "object": fiscal_profile,
            "is_update": True,
        }
        return render(request, self.template_name, context)


class FiscalProfileListView(LoginRequiredMixin, ListView):
    """Vista genérica para listar los Perfiles Fiscales asociados al usuario."""

    model = FiscalProfile
    template_name = "supplier/fiscal_profile_list.html"
    context_object_name = "object_list"

    def get_queryset(self) -> QuerySet[FiscalProfile]:
        """Filtra el conjunto de datos garantizando el aislamiento multi-inquilino."""
        return FiscalProfile.objects.filter(admin=self.request.user)


class FiscalProfileDetailView(LoginRequiredMixin, DetailView):
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


class FiscalProfileDeleteView(LoginRequiredMixin, DeleteView):
    """Vista genérica para la eliminación física de un Perfil Fiscal determinado."""

    model = FiscalProfile
    template_name = "supplier/fiscal_profile_confirm_delete.html"
    slug_field = "code"
    slug_url_kwarg = "code"
    success_url = reverse_lazy("fiscal-profile-list")

    def get_queryset(self) -> QuerySet[FiscalProfile]:
        """Previene que operadores externos eliminen perfiles ajenos."""
        return FiscalProfile.objects.filter(admin=self.request.user)