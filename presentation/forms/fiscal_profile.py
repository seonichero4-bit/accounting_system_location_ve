"""Módulo de formularios para la gestión de perfiles fiscales y entidades contables."""

from django import forms

from data_access.models.base import FiscalProfile
from django_ledger.models import EntityModel


class FiscalProfileForm(forms.ModelForm):
    """Formulario mapeado al modelo FiscalProfile para el control tributario."""

    class Meta:
        """Configuraciones del modelo FiscalProfile."""

        model = FiscalProfile
        fields = ["code", "name", "rif", "nit", "taxpayer_type"]


class EntityModelForm(forms.ModelForm):
    """Formulario mapeado al modelo EntityModel de Django Ledger."""

    use_accrual_method = forms.BooleanField(required=False)
    fy_start_month = forms.IntegerField()

    class Meta:
        """Configuraciones del modelo EntityModel exponiendo los campos solicitados."""

        model = EntityModel
        fields = ["name"]