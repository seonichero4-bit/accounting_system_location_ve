"""Módulo de servicios para la gestión de perfiles fiscales.

Implementa la capa de servicios encargada de encapsular la lógica de negocio
y orquestar la creación de perfiles fiscales, sus entidades contables asociadas
y el periodo fiscal inicial, manteniendo un aislamiento estricto entre la capa 
de presentación y el acceso a datos.
"""

from datetime import date
from typing import Any, Optional

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from data_access.models.base import FiscalPeriod, FiscalProfile

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

        Recibe los datos procesados de forma explícita y delega la ejecución 
        transaccional a la capa de datos, creando la entidad contable y el
        periodo fiscal de inicio si este es provisto.

        Args:
            entity_name (str): Nombre explícito y legal para la entidad contable.
            use_accrual_method (bool): Define si la entidad usa el método de devengado.
            fy_start_month (int): Mes de inicio del año fiscal (1-12).
            rif (str): Registro de Información Fiscal.
            taxpayer_type (str): Tipo de contribuyente (ej. 'ORDINARY', 'SPECIAL').
            start_period (Optional[date], optional): Fecha de inicio del periodo fiscal.

        Returns:
            FiscalProfile: La instancia del perfil fiscal recién creada.

        Raises:
            ValueError: Si ocurre una violación de integridad de datos o validación.
        """
        try:
            return FiscalProfile.create_profile(
                admin=self.admin_user,
                entity_name=entity_name,
                use_accrual_method=use_accrual_method,
                fy_start_month=fy_start_month,
                rif=rif,
                taxpayer_type=taxpayer_type,
                start_period=start_period,
            )
        except (IntegrityError, ValidationError) as error:
            raise ValueError(
                f"Error de negocio al procesar la creación del perfil fiscal: {str(error)}"
            ) from error

    def update_fiscal_profile(
        self,
        fiscal_profile: FiscalProfile,
        entity_name: Any = _UNSET,
        use_accrual_method: Any = _UNSET,
        fy_start_month: Any = _UNSET,
        rif: Any = _UNSET,
        taxpayer_type: Any = _UNSET,
        start_period: Any = _UNSET,
    ) -> FiscalProfile:
        """Orquesta la actualización atómica del perfil fiscal, su entidad contable y su periodo fiscal.

        Deriva la entidad directamente desde el perfil fiscal suministrado gracias
        a su relación OneToOneField bidireccional y gestiona el periodo fiscal inicial.

        Args:
            fiscal_profile (FiscalProfile): Instancia actual del perfil fiscal.
            entity_name (str, optional): Nuevo nombre legal para la entidad contable.
            use_accrual_method (bool, optional): Modifica el método de devengado.
            fy_start_month (int, optional): Modifica el mes de inicio fiscal.
            rif (str, optional): Nuevo Registro de Información Fiscal.
            taxpayer_type (str, optional): Nuevo tipo de contribuyente.
            start_period (date, optional): Nueva fecha de inicio para el periodo fiscal.

        Returns:
            FiscalProfile: La instancia del perfil fiscal actualizada.

        Raises:
            ValueError: Si ocurre un error de integridad o validación.
        """
        try:
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

                if rif is not _UNSET:
                    fiscal_profile.rif = rif
                if taxpayer_type is not _UNSET:
                    fiscal_profile.taxpayer_type = taxpayer_type

                # Actualización o creación del periodo fiscal inicial
                if start_period is not _UNSET:
                    if fiscal_profile.initial_fiscal_period:
                        period = fiscal_profile.initial_fiscal_period
                        period.start_period = start_period
                        period.save()
                        
                fiscal_profile.save()
                return fiscal_profile

        except (IntegrityError, ValidationError) as error:
            raise ValueError(
                f"Error de negocio al actualizar el perfil fiscal: {str(error)}"
            ) from error