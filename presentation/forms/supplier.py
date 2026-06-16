"""Módulo de formularios para la gestión de proveedores locales."""

from django import forms
from accounting_system_ve.data_access.models.supplier import ProveedorLocal


class ProveedorLocalForm(forms.ModelForm):
    """Formulario nativo para la creación y edición de ProveedorLocal.
    
    Excluye el perfil fiscal ya que este se inyecta desde la vista base
    garantizando el aislamiento del inquilino (tenant).
    """

    class Meta:
        model = ProveedorLocal
        exclude = ["fiscal_profile"]
        widgets = {
            "codigo": forms.TextInput(attrs={"class": "form-control"}),
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "rif": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_proveedor": forms.Select(attrs={"class": "form-control"}),
            "retencion_usual": forms.TextInput(attrs={"class": "form-control"}),
            "porcentaje_retencion_iva": forms.NumberInput(attrs={"class": "form-control"}),
            "porcentaje_ari": forms.NumberInput(attrs={"class": "form-control"}),
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
        patron_rif = re.compile(r"^[VJEGPC]-\d{8}-\d$")
        
        if not patron_rif.match(rif):
            raise ValidationError(
                "Formato de RIF inválido. Debe seguir el patrón 'X-00000000-0' "
                "(ej. J-12345678-9 o V-12345678-9)."
            )
            
        return rif