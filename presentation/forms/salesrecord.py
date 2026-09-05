"""Módulo de formularios para la gestión del modelo SalesRecord."""

from typing import Any

from django import forms

from data_access.models.customer import Customer
from data_access.models.sales_record import SalesRecord


class SalesRecordForm(forms.ModelForm):
    """Formulario para la creación y actualización de registros de venta.

    Aplica aislamiento de inquilinos (tenants) filtrando las relaciones
    de clave foránea e impide la manipulación de los datos fiscales base.
    """

    class Meta:
        model = SalesRecord
        fields = '__all__'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Inicializa el formulario inyectando el contexto del tenant.
        
        Extrae `fiscal_profile` y `fiscal_period` de los argumentos para
        filtrar las opciones válidas y bloquear campos críticos.
        """
        fiscal_profile = kwargs.pop('fiscal_profile', None)
        fiscal_period = kwargs.pop('fiscal_period', None)

        super().__init__(*args, **kwargs)

        if fiscal_profile:
            # 1. Asignación directa e inmutable a la instancia
            self.instance.fiscal_profile = fiscal_profile
            
            # 2. Aislamiento estricto de QuerySets (Multi-tenant)
            if 'affected_invoice' in self.fields:
                self.fields['affected_invoice'].queryset = SalesRecord.objects.filter(
                    fiscal_profile=fiscal_profile
                )
            if 'client' in self.fields:
                self.fields['client'].queryset = Customer.objects.filter(
                    fiscal_profile=fiscal_profile
                )

        if fiscal_period:
            self.instance.fiscal_period = fiscal_period

        # 3. Bloqueo visual e inhibición de manipulación desde el HTML
        for field_name in ['fiscal_profile', 'fiscal_period']:
            if field_name in self.fields:
                self.fields[field_name].widget = forms.HiddenInput()
                self.fields[field_name].disabled = True