import json
from typing import List, Dict, Any


from django.db import transaction
from django_ledger.io import roles

from data_access.models.base import FiscalProfile 

class ChartOfAccountsImportService:
    """Servicio para la creación del Plan de Cuentas (CoA) e importación masiva 

    de cuentas contables para la entidad de un Perfil Fiscal.
    """

    def __init__(self, fiscal_profile: FiscalProfile):
        self.fiscal_profile = fiscal_profile
        self.entity = fiscal_profile.entity

    def import_accounts_from_data(
        self, 
        accounts_data: List[Dict[str, Any]], 
        coa_name: str = "Plan de Cuentas Personalizado"
    ) -> int:
        """Crea el Chart of Accounts (si no existe) e inserta las cuentas contables de forma atómica.

        Args:
            accounts_data (List[Dict[str, Any]]): Lista de diccionarios con la estructura de cuentas.
            coa_name (str): Nombre opcional para el libro de cuentas.

        Returns:
            int: Cantidad de cuentas creadas exitosamente.

        Raises:
            ValueError: Si el perfil fiscal no posee una entidad contable asociada.
        """
        if not self.entity:
            raise ValueError("El perfil fiscal actual no tiene una entidad (EntityModel) asociada.")

        with transaction.atomic():
            # 1. Obtener o crear el Chart of Accounts usando la API oficial de django-ledger
            coa_qs = self.entity.get_coa_model_qs(active=True)
            
            if coa_qs.exists():
                coa_model = coa_qs.first()
            else:
                coa_model = self.entity.create_chart_of_accounts(
                    coa_name=coa_name,
                    assign_as_default=True,
                    commit=True
                )

            # 2. Inserción masiva de cuentas mediante la API de la entidad
            processed_count = 0
            for acc in accounts_data:

            # 3. Obtener el objeto real del módulo/Enum de roles
                role_obj = getattr(roles, acc["role"], acc["role"])
                balance_obj = getattr(roles, acc["balance_type"], acc["balance_type"])

                self.entity.create_account(
                    coa_model=coa_model,
                    code=str(acc["code"]),
                    name=acc["name"],
                    role=role_obj,
                    balance_type=balance_obj,
                    active=acc.get("active", True)
                    )
            processed_count += 1

            return processed_count