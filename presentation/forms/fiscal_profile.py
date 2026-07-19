"""Módulo de formularios para la gestión de perfiles fiscales y entidades contables."""

from django import forms

from data_access.models.base import FiscalProfile
from django_ledger.models import EntityModel


class FiscalProfileForm(forms.ModelForm):
    """Formulario mapeado al modelo FiscalProfile para el control tributario."""

    class Meta:
        """Configuraciones del modelo FiscalProfile."""

        model = FiscalProfile
        fields = ["name", "rif", "taxpayer_type"]


class EntityModelForm(forms.ModelForm):
    """Formulario mapeado al modelo EntityModel de Django Ledger."""

    use_accrual_method = forms.BooleanField(
        initial=True, 
        required=False
    )
    fy_start_month = forms.IntegerField(
        initial=12,
        min_value=1,
        max_value=12
    )

    class Meta:
        """Configuraciones del modelo EntityModel exponiendo los campos solicitados."""

        model = EntityModel
        fields = ["name"]