"""Módulo de formularios para la gestión del modelo SalesRecord."""

from typing import Any

from django import forms

from data_access.models.customer import Customer
from data_access.models.sales_record import SalesRecord
from presentation.mixins.fiscalcontextformmixin import FiscalContextFormMixin


class SalesRecordForm(FiscalContextFormMixin, forms.ModelForm):
    class Meta:
        model = SalesRecord
        exclude = ['fiscal_profile', 'fiscal_period']

    def __init__(self, *args: Any, **kwargs: Any) -> None:
    
        super().__init__(*args, **kwargs)

    
        # Filtrado de QuerySets usando el atributo de la clase
        if self.fiscal_profile:
            if 'affected_invoice' in self.fields:
                self.fields['affected_invoice'].queryset = SalesRecord.objects.filter(
                    fiscal_profile=self.fiscal_profile
                )
            if 'client' in self.fields:
                self.fields['client'].queryset = Customer.objects.filter(
                    fiscal_profile=self.fiscal_profile
                )
