"""Módulo de servicios para la gestión de perfiles fiscales.

Implementa la capa de servicios encargada de encapsular la lógica de negocio
y orquestar la creación de perfiles fiscales y sus entidades contables asociadas,
manteniendo un aislamiento estricto entre la capa de presentación y el acceso a datos.
"""

from typing import Any, Optional

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from data_access.models.base import FiscalProfile


class FiscalProfileService:
    """Servicio encargado de coordinar la lógica de negocio para los perfiles fiscales.

    Actúa como intermediario orquestando la instanciación transaccional
    del perfil fiscal y su entidad base asociada, aislando el contexto del 
    usuario operador inyectado desde la capa de presentación.
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
        rif: str,
        code: str,
        taxpayer_type: str,
        nit: Optional[str] = None,
        **entity_kwargs: Any
    ) -> FiscalProfile:
        """Orquesta la creación de un perfil fiscal utilizando el usuario inyectado.

        Recibe los datos procesados desde el formulario en la capa de presentación 
        y delega la ejecución transaccional a la capa de datos, aplicando el 
        usuario almacenado en el contexto del servicio.

        Args:
            entity_name (str): Nombre explícito y legal para la entidad contable.
            rif (str): Registro de Información Fiscal.
            code (str): Código de control interno único.
            taxpayer_type (str): Tipo de contribuyente (ej. 'ORDINARY', 'SPECIAL').
            nit (Optional[str], optional): Número de Identificación Tributaria.
            **entity_kwargs (Any): Argumentos adicionales para la entidad contable.

        Returns:
            FiscalProfile: La instancia del perfil fiscal recién creada.

        Raises:
            ValueError: Si ocurre una violación de integridad de datos o validación.
        """
        try:
            return FiscalProfile.create_profile(
                admin=self.admin_user,
                entity_name=entity_name,
                rif=rif,
                code=code,
                taxpayer_type=taxpayer_type,
                nit=nit,
                **entity_kwargs
            )
        except (IntegrityError, ValidationError) as error:
            raise ValueError(
                f"Error de negocio al procesar la creación del perfil fiscal: {str(error)}"
            ) from error

    def update_fiscal_profile(
        self,
        fiscal_profile: FiscalProfile,
        entity: Any,
        profile_data: dict[str, Any],
        entity_data: dict[str, Any]
    ) -> FiscalProfile:
        """Orquesta la actualización atómica del perfil fiscal y su entidad contable.

        Args:
            fiscal_profile (FiscalProfile): Instancia actual del perfil fiscal.
            entity (Any): Instancia de EntityModel asociada.
            profile_data (dict): Datos limpios del formulario del perfil fiscal.
            entity_data (dict): Datos limpios del formulario de EntityModel.

        Returns:
            FiscalProfile: La instancia del perfil fiscal actualizada.

        Raises:
            ValueError: Si ocurre un error de integridad o validación.
        """
        try:
            with transaction.atomic():
                if entity:
                    for key, value in entity_data.items():
                        setattr(entity, key, value)
                    entity.save()

                for key, value in profile_data.items():
                    setattr(fiscal_profile, key, value)
                fiscal_profile.save()

                return fiscal_profile
        except (IntegrityError, ValidationError) as error:
            raise ValueError(
                f"Error de negocio al actualizar el perfil fiscal: {str(error)}"
            ) from error