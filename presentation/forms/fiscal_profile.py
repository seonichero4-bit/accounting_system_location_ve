"""Módulo de formularios para la gestión de perfiles fiscales, entidades contables y periodos fiscales."""

import calendar
from django import forms
from datetime import datetime, date

from data_access.models.base import FiscalProfile, FiscalPeriod
from django_ledger.models import EntityModel


class FiscalPeriodForm(forms.ModelForm):
    # Cambiamos a DateField con widget type="date" para permitir seleccionar días específicos
    start_period = forms.DateField(
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "type": "date",
                "class": "form-control",
            },
        ),
        input_formats=["%Y-%m-%d"],
        label="Periodo Fiscal de Inicio",
        help_text="Seleccione la fecha de inicio del período",
    )

    class Meta:
        model = FiscalPeriod
        fields = ["start_period"]

    def __init__(self, *args, taxpayer_type=None, **kwargs):
        """Acepta un argumento opcional `taxpayer_type` para validar según el tipo de contribuyente."""
        self.taxpayer_type = taxpayer_type
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.start_period:
            self.initial["start_period"] = self.instance.start_period.strftime("%Y-%m-%d")

    def clean_start_period(self):
        data = self.cleaned_data.get("start_period")
        if not data:
            return None

        # Si viene como string
        if isinstance(data, str):
            try:
                data = datetime.strptime(data, "%Y-%m-%d").date()
            except ValueError:
                raise forms.ValidationError("Formato de fecha inválido. Use el formato YYYY-MM-DD.")

        year = data.year
        month = data.month
        day = data.day
        _, last_day = calendar.monthrange(year, month)

        # Validación según el tipo de contribuyente (si se proporciona en la inicialización)
        if self.taxpayer_type:
            if self.taxpayer_type in [FiscalProfile.TaxpayerType.FORMAL, FiscalProfile.TaxpayerType.ORDINARY]:
                if day != 1:
                    raise forms.ValidationError(
                        "Para contribuyentes de tipo Ordinario y Formal (periodos mensuales), "
                        "la fecha de inicio debe ser el día 01 del mes."
                    )
            elif self.taxpayer_type == FiscalProfile.TaxpayerType.SPECIAL:
                if day not in (15, last_day):
                    raise forms.ValidationError(
                        "Para contribuyentes de tipo Especial (periodos quincenales), "
                        "la fecha de inicio debe ser el día 15 o el final de mes."
                    )
        else:
            # Validación general en caso de no especificarse el tipo
            if day not in (1, 15, last_day):
                raise forms.ValidationError(
                    "La fecha debe ser inicio de mes (día 01) para periodos mensuales, "
                    "o día 15 / final de mes para periodos quincenales."
                )

        return data

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