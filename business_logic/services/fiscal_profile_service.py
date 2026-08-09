"""Módulo de servicios para la gestión de perfiles fiscales.

Implementa la capa de servicios encargada de encapsular la lógica de negocio
y orquestar la creación de perfiles fiscales, sus entidades contables asociadas
y el periodo fiscal inicial, manteniendo un aislamiento estricto entre la capa 
de presentación y el acceso a datos.
"""

from datetime import date
from typing import Any, Optional

from django.contrib.auth.models import User
from django.db import transaction

# Asumiendo los imports de tus modelos basados en la estructura proporcionada
from data_access.models.base import FiscalPeriod, FiscalProfile
from django_ledger.models import EntityModel

# Centinela para identificar argumentos no provistos en la actualización
_UNSET = object()


class FiscalProfileService:
    """Servicio encargado de coordinar la lógica de negocio para los perfiles fiscales.

    Actúa como intermediario orquestando la instanciación transaccional
    del perfil fiscal, su entidad base asociada y el periodo fiscal de inicio,
    aislando el contexto del usuario operador inyectado desde la capa de presentación.
    """

    def __init__(self, admin_user: User) -> None:
        """Inicializa el servicio inyectando el usuario operador.

        Args:
            admin_user (User): Instancia del usuario autenticado proveniente de la vista.
        """
        self.admin_user = admin_user

    def create_fiscal_profile(
        self,
        entity_name: str,
        use_accrual_method: bool,
        fy_start_month: int,
        rif: str,
        taxpayer_type: str,
        start_period: Optional[date] = None,
    ) -> FiscalProfile:
        """Orquesta la creación de un perfil fiscal utilizando el usuario inyectado.

        Recibe los datos procesados de forma explícita y ejecuta de forma 
        transaccional la creación de la entidad contable, el periodo fiscal de
        inicio (si es provisto) y el perfil fiscal.

        Args:
            entity_name (str): Nombre explícito y legal para la entidad contable.
            use_accrual_method (bool): Define si la entidad usa el método de devengado.
            fy_start_month (int): Mes de inicio del año fiscal (1-12).
            rif (str): Registro de Información Fiscal.
            taxpayer_type (str): Tipo de contribuyente (ej. 'ORDINARY', 'SPECIAL').
            start_period (Optional[date], optional): Fecha de inicio del periodo fiscal.

        Returns:
            FiscalProfile: La instancia del perfil fiscal recién creada.
        """
        with transaction.atomic():
            entity = EntityModel.create_entity(
                name=entity_name,
                admin=self.admin_user,
                use_accrual_method=use_accrual_method,
                fy_start_month=fy_start_month
            )

            initial_period = None
            if start_period:
                initial_period = FiscalPeriod.objects.create(
                    start_period=start_period,
                    status=FiscalPeriod.Status.PRELIMINARY
                )

            profile = FiscalProfile.objects.create(
                entity=entity,
                name=entity_name,
                rif=rif,
                taxpayer_type=taxpayer_type,
                initial_fiscal_period=initial_period
            )
            return profile

    def update_fiscal_profile(
        self,
        fiscal_profile: FiscalProfile,
        entity_name: Any = _UNSET,
        use_accrual_method: Any = _UNSET,
        fy_start_month: Any = _UNSET,
        rif: Any = _UNSET,
        taxpayer_type: Any = _UNSET,
        start_period: Any = _UNSET,
        ledger: Any = _UNSET,
        inventory_account: Any = _UNSET,
        vat_credit_account: Any = _UNSET,
        igtf_expense_account: Any = _UNSET,
        islr_payable_account: Any = _UNSET,
        cxp_suppliers_account: Any = _UNSET,
        vat_withheld_payable_account: Any = _UNSET,
    ) -> FiscalProfile:
        """Orquesta la actualización atómica del perfil fiscal, su entidad contable y su periodo fiscal.

        Deriva la entidad directamente desde el perfil fiscal suministrado gracias
        a su relación OneToOneField bidireccional, y gestiona la actualización
        de los campos de Libro Mayor y Cuentas de Control.

        Args:
            fiscal_profile (FiscalProfile): Instancia actual del perfil fiscal.
            entity_name (str, optional): Nuevo nombre legal para la entidad contable.
            use_accrual_method (bool, optional): Modifica el método de devengado.
            fy_start_month (int, optional): Modifica el mes de inicio fiscal.
            rif (str, optional): Nuevo Registro de Información Fiscal.
            taxpayer_type (str, optional): Nuevo tipo de contribuyente.
            start_period (date, optional): Nueva fecha de inicio para el periodo fiscal.
            ledger (Any, optional): Libro Mayor General.
            inventory_account (Any, optional): Cuenta contable de control para Inventario de Mercancía.
            vat_credit_account (Any, optional): Cuenta contable para IVA Crédito Fiscal Computable.
            igtf_expense_account (Any, optional): Cuenta contable para IGTF Pagado en Compras.
            islr_payable_account (Any, optional): Cuenta contable para Retención de ISLR por Pagar.
            cxp_suppliers_account (Any, optional): Cuenta contable Cuentas por Pagar Proveedores.
            vat_withheld_payable_account (Any, optional): Cuenta contable para IVA Retenido por Enterar.

        Returns:
            FiscalProfile: La instancia del perfil fiscal actualizada.
        """
        with transaction.atomic():
            # Acceso directo a la entidad a través del OneToOneField mapeado
            entity = fiscal_profile.entity
            
            if entity:
                if entity_name is not _UNSET:
                    entity.name = entity_name
                    fiscal_profile.name = entity_name
                if use_accrual_method is not _UNSET:
                    entity.use_accrual_method = use_accrual_method
                if fy_start_month is not _UNSET:
                    entity.fy_start_month = fy_start_month
                entity.save()

            # Atributos fiscales
            if rif is not _UNSET:
                fiscal_profile.rif = rif
            if taxpayer_type is not _UNSET:
                fiscal_profile.taxpayer_type = taxpayer_type

            # Configuración de Libro Mayor y Cuentas de Control
            if ledger is not _UNSET:
                fiscal_profile.ledger = ledger
            if inventory_account is not _UNSET:
                fiscal_profile.inventory_account = inventory_account
            if vat_credit_account is not _UNSET:
                fiscal_profile.vat_credit_account = vat_credit_account
            if igtf_expense_account is not _UNSET:
                fiscal_profile.igtf_expense_account = igtf_expense_account
            if islr_payable_account is not _UNSET:
                fiscal_profile.islr_payable_account = islr_payable_account
            if cxp_suppliers_account is not _UNSET:
                fiscal_profile.cxp_suppliers_account = cxp_suppliers_account
            if vat_withheld_payable_account is not _UNSET:
                fiscal_profile.vat_withheld_payable_account = vat_withheld_payable_account

            # Actualización o creación del periodo fiscal inicial
            if start_period is not _UNSET:
                if fiscal_profile.initial_fiscal_period:
                    period = fiscal_profile.initial_fiscal_period
                    period.start_period = start_period
                    period.save()
                    
            fiscal_profile.save()
            return fiscal_profile