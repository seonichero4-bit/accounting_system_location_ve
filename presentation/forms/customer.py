"""Formulario para la gestión de Clientes (Customer).

Controla la validación a nivel de presentación, la exclusión de campos
protegidos (como el perfil fiscal) y el filtrado dinámico de cuentas
contables según el Tenant actual.
"""

from typing import Any, Dict

from django import forms

from data_access.models.customer import Customer
from django_ledger.models import AccountModel


class CustomerForm(forms.ModelForm):
    """Formulario de creación y actualización para el modelo Customer."""

    class Meta:
        """Configuración de metadatos del formulario."""
        model = Customer
        exclude = ['fiscal_profile']

    def __init__(self, *args: Any, **kwargs: Dict[str, Any]) -> None:
        """Inicializa el formulario inyectando el perfil fiscal y filtrando cuentas.
        
        Args:
            fiscal_profile: Instancia del perfil fiscal del inquilino actual extraída
                            de los kwargs proporcionados por la vista.
        """
        fiscal_profile = kwargs.pop('fiscal_profile', None)
        super().__init__(*args, **kwargs)

        # Si se inyecta por kwargs (Creación/Actualización) o ya existe en la instancia
        active_profile = fiscal_profile or getattr(self.instance, 'fiscal_profile', None)

        if active_profile:
            # Forzamos la asignación a la instancia para evitar manipulación externa
            self.instance.fiscal_profile = active_profile

            # Filtramos los QuerySets usando el Ledger del Tenant actual
            if hasattr(active_profile, 'ledger') and active_profile.ledger:
                tenant_accounts = AccountModel.objects.filter(ledger=active_profile.ledger)
                self.fields['custom_accounts_receivable'].queryset = tenant_accounts
                self.fields['custom_income_account'].queryset = tenant_accounts