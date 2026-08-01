from django import forms
from django.db import models
from data_access.models.fiscalperiod import FiscalPeriod
from data_access.models.base import FiscalProfile


class FiscalPeriodSelectionForm(forms.Form):
    fiscal_period = forms.ModelChoiceField(
        queryset=FiscalPeriod.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="-- Seleccione un Período Fiscal --",
        label="Período Fiscal Activo",
        required=True
    )

    def __init__(self, *args, fiscal_profile: FiscalProfile | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if fiscal_profile:
            # Consulta los períodos fiscales asociados al perfil fiscal activo
            if hasattr(fiscal_profile, 'initial_fiscal_period'):
                qs = FiscalPeriod.objects.filter(fiscal_profiles=fiscal_profile).order_by('id')

                self.fields['fiscal_period'].queryset = qs

            ## Se debe manejar la excepcion

            # Construcción dinámica de etiquetas:
            # 1. El primer (y único) registro inicial muestra `start_period`.
            # 2. Los registros subsecuentes muestran `subsequent_period`.
            choices = [('', self.fields['fiscal_period'].empty_label)]
            for idx, period in enumerate(qs):
                status_display = period.get_status_display()
                if idx == 0:
                    label = f"{period.start_period} ({status_display})"
                else:
                    date_val = period.subsequent_period or period.start_period
                    label = f"{date_val} ({status_display})"
                
                choices.append((period.pk, label))

            self.fields['fiscal_period'].choices = choices