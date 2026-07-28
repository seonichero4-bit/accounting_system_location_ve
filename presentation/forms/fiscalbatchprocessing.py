from django import forms
from django.core.validators import RegexValidator

period_validator = RegexValidator(
    regex=r"^(0[1-9]|1[0-2])-\d{4}$",
    message="El período fiscal debe cumplir con el formato estricto MM-YYYY (ejemplo: 07-2026).",
    code="invalid_period_format",
)


class FiscalBatchProcessingForm(forms.Form):
    """Formulario para la selección y disparo del procesamiento contable en lote."""

    application_month_year = forms.CharField(
        label="Período Fiscal",
        max_length=7,
        validators=[period_validator],
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg text-center fw-bold",
                "placeholder": "MM-YYYY",
                "autocomplete": "off",
                "pattern": r"^(0[1-9]|1[0-2])-\d{4}$",
            }
        ),
        help_text="Indique el mes y año en formato MM-YYYY (ej. 07-2026) correspondiente al lote preliminar a cerrar.",
    )

    def clean_application_month_year(self) -> str:
        """Sanea y normaliza la cadena del período fiscal."""
        period = self.cleaned_data["application_month_year"].strip()
        return period