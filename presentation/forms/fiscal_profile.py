"""Módulo de formularios para la gestión de perfiles fiscales, entidades contables y periodos fiscales."""

from django import forms
from datetime import datetime, date

from data_access.models.base import FiscalProfile, FiscalPeriod
from django_ledger.models import EntityModel


class FiscalPeriodForm(forms.ModelForm):
    # Definimos un CharField o DateField personalizado para capturar YYYY-MM
    start_period = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "type": "month",  # Selector de solo Mes y Año en HTML5
                "class": "form-control",
            }
        ),
        label="Periodo Fiscal de Inicio",
        help_text="Seleccione mes y año"
    )

    class Meta:
        model = FiscalPeriod
        fields = ["start_period"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Al editar, formateamos el valor actual de date (YYYY-MM-01) a string 'YYYY-MM'
        if self.instance and self.instance.start_period:
            self.initial['start_period'] = self.instance.start_period.strftime('%Y-%m')

    def clean_start_period(self):
        data = self.cleaned_data.get("start_period")
        if not data:
            return None
        
        # Si ya es un objeto date, retornamos normalizado al día 1
        if isinstance(data, date):
            return date(data.year, data.month, 1)

        # Si viene como string del widget 'YYYY-MM'
        try:
            parsed_date = datetime.strptime(data, "%Y-%m").date()
            return date(parsed_date.year, parsed_date.month, 1)
        except ValueError:
            raise forms.ValidationError("Formato de período inválido. Use el formato YYYY-MM.")

class FiscalProfileForm(forms.ModelForm):
    """Formulario mapeado al modelo FiscalProfile para el control tributario."""

    class Meta:
        model = FiscalProfile
        fields = ["name", "rif", "taxpayer_type"]


class EntityModelForm(forms.ModelForm):
    """Formulario mapeado al modelo EntityModel de Django Ledger."""

    use_accrual_method = forms.BooleanField(initial=True, required=False)
    fy_start_month = forms.IntegerField(initial=12, min_value=1, max_value=12)

    class Meta:
        model = EntityModel
        fields = ["name"]