from django import forms
from data_access.models.base import FiscalProfile

class FiscalProfileSelectionForm(forms.Form):
    fiscal_profile = forms.ModelChoiceField(
        queryset=FiscalProfile.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="-- Seleccione un Perfil Fiscal --",
        label="Perfil Fiscal Activo",
        required=True
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            # Filtra perfiles fiscales asociados a las entidades administradas por el usuario
            self.fields['fiscal_profile'].queryset = FiscalProfile.objects.filter(
                entity__admin=user
            ).select_related('entity')