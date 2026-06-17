"""Módulo de formularios para la gestión de proveedores locales."""

import re
from django import forms
from django.core.exceptions import ValidationError
from data_access.models.supplier import LocalSupplier


class LocalSupplierForm(forms.ModelForm):
    """Formulario nativo para la creación y edición de ProveedorLocal.
    
    Excluye el perfil fiscal ya que este se inyecta desde la vista base
    garantizando el aislamiento del inquilino (tenant).
    """

    class Meta:
        model = LocalSupplier
        exclude = ["fiscal_profile"]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "rif": forms.TextInput(attrs={"class": "form-control"}),
            "supplier_type": forms.Select(attrs={"class": "form-control"}),
            "usual_withholding": forms.TextInput(attrs={"class": "form-control"}),
            "vat_withholding_percentage": forms.NumberInput(attrs={"class": "form-control"}),
            "ari_percentage": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def clean_rif(self) -> str:
        """Valida estructuralmente el RIF mediante expresiones regulares.

        Asegura que el Registro de Información Fiscal cumpla con el estándar
        nacional venezolano (ej. J-12345678-9 o V-12345678-9), convirtiéndolo
        a mayúsculas automáticamente de forma previa a la evaluación.

        Returns:
            str: El RIF validado y formateado en mayúsculas.

        Raises:
            ValidationError: Si el RIF no coincide con el patrón establecido.
        """
        rif = self.cleaned_data.get("rif", "").strip().upper()
        
        # Patrón: Letra inicial (V, J, E, G, P, C) seguida de guion, 8 dígitos, guion y 1 dígito.
        rif_pattern = re.compile(r"^[VJEGPC]-\d{8}-\d$")
        
        if not rif_pattern.match(rif):
            raise ValidationError(
                "Formato de RIF inválido. Debe seguir el patrón 'X-00000000-0' "
                "(ej. J-12345678-9 o V-12345678-9)."
            )
            
        return rif