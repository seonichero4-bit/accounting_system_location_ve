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
        
 