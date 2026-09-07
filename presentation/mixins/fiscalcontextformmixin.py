from typing import Any
from django import forms

class FiscalContextFormMixin:
    """
    Mixin para formularios que requieren perfil y período fiscal.
    Inyecta estos valores en la instancia al crear, y los respeta al editar.
    """
    # Se deben excluir campos "fiscal_profile" y "fiscal_period"
        # exclude['fiscal_profile', 'fiscal_period']

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.fiscal_profile = kwargs.pop('fiscal_profile', None)
        self.fiscal_period = kwargs.pop('fiscal_period', None)
        
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            # Modo Edición: Bloqueamos los valores al estado actual de la base de datos
            self.fiscal_profile = self.instance.fiscal_profile
            self.fiscal_period = self.instance.fiscal_period
        else:
            # Modo Creación: Asignamos a la instancia para que se guarden en DB
            self.instance.fiscal_profile = self.fiscal_profile
            self.instance.fiscal_period = self.fiscal_period