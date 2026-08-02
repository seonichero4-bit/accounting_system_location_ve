"""Módulo de formularios para la gestión de retenciones fiscales de IVA."""
from typing import Any

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
        fields = ["application_date", 
                  "vat_withholding_percentage", 
                  "document_number"
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fiscal_period'].required = False
    
    def add_error(self, field, error):
        from django.core.exceptions import ValidationError
        
        # Captura errores arrojados por el modelo vinculados a 'purchase_invoice'
        if field is None and hasattr(error, "error_dict") and "purchase_invoice" in error.error_dict:
            pi_errors = error.error_dict.pop("purchase_invoice")
            if self._errors is None:
                self._errors = self.error_class()
            self._errors["purchase_invoice"] = self.error_class([m.message for m in pi_errors])
            
        elif field == "purchase_invoice":
            if self._errors is None:
                self._errors = self.error_class()
            msg = error.message if hasattr(error, "message") else str(error)
            self._errors["purchase_invoice"] = self.error_class([msg])
            return
            
        super().add_error(field, error)