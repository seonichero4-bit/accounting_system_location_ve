"""Módulo de vistas para el ciclo CRUD completo de Perfiles Fiscales.

Combina vistas personalizadas para flujos de formularios múltiples y complejos
con vistas genéricas de Django para operaciones estándar de lectura y eliminación.
"""

from typing import Any

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView

from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.base import FiscalProfile
from presentation.forms.fiscal_profile import EntityModelForm, FiscalProfileForm, FiscalPeriodForm
from ..mixins.requestscopedquerysetmixin import RequestScopedQuerySetMixin 

class FiscalProfileCreateView(View):
    """Vista para la creación conjunta de FiscalProfile, EntityModel y FiscalPeriod."""

    template_name = "fiscal_profile_form.html"

    def get(self, request, *args, **kwargs):
        profile_form = FiscalProfileForm()
        entity_form = EntityModelForm()
        period_form = FiscalPeriodForm()
        return render(
            request, 
            self.template_name,
            {
                "profile_form": profile_form,
                "entity_form": entity_form,
                "period_form": period_form,
            },
        )

    def post(self, request, *args, **kwargs):
        profile_form = FiscalProfileForm(request.POST)
        entity_form = EntityModelForm(request.POST)

        # Se recupera taxpayer_type desde los datos recibidos en el POST
        taxpayer_type = request.POST.get("taxpayer_type")
        period_form = FiscalPeriodForm(request.POST, taxpayer_type=taxpayer_type)

        if profile_form.is_valid() and entity_form.is_valid() and period_form.is_valid():
            service = FiscalProfileService(admin_user=request.user)
            try:
                service.create_fiscal_profile(
                    entity_name=entity_form.cleaned_data["name"],
                    use_accrual_method=entity_form.cleaned_data["use_accrual_method"],
                    fy_start_month=entity_form.cleaned_data["fy_start_month"],
                    rif=profile_form.cleaned_data["rif"],
                    taxpayer_type=profile_form.cleaned_data["taxpayer_type"],
                    start_period=period_form.cleaned_data.get("start_period"),
                )
                return redirect("fiscal-profile-list")
            except (ValueError, ValidationError) as error:
                if hasattr(error, "message_dict"):
                    for field, errors in error.message_dict.items():
                        for err in errors:
                            if field in profile_form.fields:
                                profile_form.add_error(field, err)
                            elif field in period_form.fields:
                                period_form.add_error(field, err)
                            else:
                                profile_form.add_error(None, err)
                else:
                    profile_form.add_error(None, str(error))

        return render(
            request,
            self.template_name,
            {
                "profile_form": profile_form,
                "entity_form": entity_form,
                "period_form": period_form,
            },
        )


class FiscalProfileUpdateView(View):
    """Vista para la actualización conjunta de FiscalProfile, EntityModel y FiscalPeriod."""

    template_name = "fiscal_profile_form.html"

    def get(self, request, pk, *args, **kwargs):
        fiscal_profile = get_object_or_404(FiscalProfile, pk=pk)
        profile_form = FiscalProfileForm(instance=fiscal_profile)

        entity_initial = {}
        if fiscal_profile.entity:
            entity_initial = {
                "use_accrual_method": fiscal_profile.entity.use_accrual_method,
                "fy_start_month": fiscal_profile.entity.fy_start_month,
            }
        entity_form = EntityModelForm(instance=fiscal_profile.entity, initial=entity_initial)

        # Se pasa taxpayer_type guardado en la instancia de FiscalProfile
        period_form = FiscalPeriodForm(
            instance=fiscal_profile.initial_fiscal_period,
            taxpayer_type=fiscal_profile.taxpayer_type,
        )

        return render(
            request,
            self.template_name,
            {
                "profile_form": profile_form,
                "entity_form": entity_form,
                "period_form": period_form,
                "fiscal_profile": fiscal_profile,
            },
        )

    def post(self, request, pk, *args, **kwargs):
        fiscal_profile = get_object_or_404(FiscalProfile, pk=pk)
        profile_form = FiscalProfileForm(request.POST, instance=fiscal_profile)
        entity_form = EntityModelForm(request.POST, instance=fiscal_profile.entity)

        # Se extrae taxpayer_type del POST o se mantiene el existente
        taxpayer_type = request.POST.get("taxpayer_type") or fiscal_profile.taxpayer_type

        period_form = FiscalPeriodForm(
            request.POST,
            instance=fiscal_profile.initial_fiscal_period,
            taxpayer_type=taxpayer_type,
        )

        if profile_form.is_valid() and entity_form.is_valid() and period_form.is_valid():
            service = FiscalProfileService(admin_user=request.user)
            try:
                service.update_fiscal_profile(
                    fiscal_profile=fiscal_profile,
                    entity_name=entity_form.cleaned_data["name"],
                    use_accrual_method=entity_form.cleaned_data["use_accrual_method"],
                    fy_start_month=entity_form.cleaned_data["fy_start_month"],
                    rif=profile_form.cleaned_data["rif"],
                    taxpayer_type=profile_form.cleaned_data["taxpayer_type"],
                    start_period=period_form.cleaned_data.get("start_period"),
                )
                return redirect("fiscal-profile-detail", pk=fiscal_profile.pk)
            except (ValueError, ValidationError) as error:
                if hasattr(error, "message_dict"):
                    for field, errors in error.message_dict.items():
                        for err in errors:
                            if field in profile_form.fields:
                                profile_form.add_error(field, err)
                            elif field in period_form.fields:
                                period_form.add_error(field, err)
                            else:
                                profile_form.add_error(None, err)
                else:
                    profile_form.add_error(None, str(error))

        return render(
            request,
            self.template_name,
            {
                "profile_form": profile_form,
                "entity_form": entity_form,
                "period_form": period_form,
                "fiscal_profile": fiscal_profile,
            },
        )


class FiscalProfileListView(RequestScopedQuerySetMixin, ListView):
    """Vista genérica para listar los Perfiles Fiscales asociados al usuario."""

    model = FiscalProfile
    template_name = "fiscal_profile_list.html"
    context_object_name = "object_list"


class FiscalProfileDetailView(RequestScopedQuerySetMixin, DetailView):
    """Vista genérica para exponer el desglose técnico de un Perfil Fiscal."""

    model = FiscalProfile
    template_name = "fiscal_profile_detail.html"
    context_object_name = "object"


class FiscalProfileDeleteView(RequestScopedQuerySetMixin, DeleteView):
    """Vista genérica para la eliminación física de un Perfil Fiscal determinado."""

    model = FiscalProfile
    template_name = "fiscal_profile_confirm_delete.html"
    success_url = reverse_lazy("fiscal-profile-list")