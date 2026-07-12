"""Módulo de formularios para la gestión de retenciones fiscales de IVA."""

from django import forms
from data_access.models.vat_withholding import VatWithholdingCertificate


class VatWithholdingCertificateForm(forms.ModelForm):
    """Formulario estructurado bajo ModelForm para VatWithholdingCertificate.

    Excluye campos calculados automáticos o de solo lectura del modelo
    como 'document_number' y 'vat_withheld_amount'.
    """

    class Meta:
        """Configuración meta del formulario de retención."""

        model = VatWithholdingCertificate
        fields = ["application_date", "vat_withholding_percentage"]
        widgets = {
            "application_date": forms.DateInput(attrs={"type": "date"}),
        }