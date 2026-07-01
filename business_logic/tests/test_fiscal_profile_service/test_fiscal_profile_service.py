"""Suite de pruebas unitarias para la clase FiscalProfileService.

Valida el correcto funcionamiento de los flujos felices y el manejo robusto de
casos de borde y errores transaccionales definidos en el plan de pruebas técnico.
"""

import pytest

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django_ledger.models import EntityModel

from data_access.models.base import FiscalProfile
from business_logic.services.fiscal_profile_service import FiscalProfileService

@pytest.mark.unit
@pytest.mark.django_db
class TestFiscalProfileService:
    """Contenedor de pruebas estructuradas para el servicio de perfiles fiscales."""

    # =========================================================================
    # 1. Happy Paths (Flujos Felices)
    # =========================================================================

    def test_create_fiscal_profile_omitting_nit_success(
        self, fiscal_profile_service: FiscalProfileService
    ) -> None:
        """[ID_HP_001] Valida la creación de un perfil fiscal omitiendo el NIT.

        Asegura que el parámetro por defecto permita guardar el campo como nulo.
        """
        # Arrange
        entity_name = "Corporación Alfa"
        use_accrual_method = True
        fy_start_month = 1
        rif = "J-87654321-0"
        code = "ALFA-001"
        taxpayer_type = "FORMAL"

        # Act
        profile = fiscal_profile_service.create_fiscal_profile(
            entity_name=entity_name,
            use_accrual_method=use_accrual_method,
            fy_start_month=fy_start_month,
            rif=rif,
            code=code,
            taxpayer_type=taxpayer_type,
            nit=None
        )

        # Assert
        assert profile.id is not None
        assert profile.nit is None
        assert profile.name == entity_name
        assert profile.entity.name == entity_name

    def test_update_fiscal_profile_entity_attributes_only_success(
        self,
        fiscal_profile_service: FiscalProfileService,
        sample_fiscal_profile: FiscalProfile
    ) -> None:
        """[ID_HP_002] Valida la actualización parcial de atributos de la entidad.

        Verifica que solo cambien los campos pasados de la entidad contable.
        """
        # Arrange
        new_name = "Nuevo Nombre S.A."
        new_month = 12
        original_rif = sample_fiscal_profile.rif
        original_code = sample_fiscal_profile.code

        # Act
        updated_profile = fiscal_profile_service.update_fiscal_profile(
            fiscal_profile=sample_fiscal_profile,
            entity_name=new_name,
            fy_start_month=new_month
        )

        # Assert
        assert updated_profile.name == new_name
        assert updated_profile.entity.name == new_name
        assert updated_profile.entity.fy_start_month == new_month
        assert updated_profile.rif == original_rif
        assert updated_profile.code == original_code

    def test_update_fiscal_profile_fields_only_success(
        self,
        fiscal_profile_service: FiscalProfileService,
        sample_fiscal_profile: FiscalProfile
    ) -> None:
        """[ID_HP_003] Valida la actualización parcial de campos del perfil.

        Asegura que las propiedades directas muten sin alterar la entidad contable.
        """
        # Arrange
        new_code = "NEW-CODE-99"
        new_taxpayer = "SPECIAL"
        original_entity_name = sample_fiscal_profile.entity.name
        original_fy_month = sample_fiscal_profile.entity.fy_start_month

        # Act
        updated_profile = fiscal_profile_service.update_fiscal_profile(
            fiscal_profile=sample_fiscal_profile,
            code=new_code,
            taxpayer_type=new_taxpayer
        )

        # Assert
        assert updated_profile.code == new_code
        assert updated_profile.taxpayer_type == new_taxpayer
        assert updated_profile.entity.name == original_entity_name
        assert updated_profile.entity.fy_start_month == original_fy_month

    # =========================================================================
    # 2. Edge Cases (Casos Borde y Manejo de Errores)
    # =========================================================================

    def test_create_fiscal_profile_duplicate_rif_raises_value_error(
        self,
        fiscal_profile_service: FiscalProfileService,
        sample_fiscal_profile: FiscalProfile
    ) -> None:
        """[ID_EC_001] Evalúa el error de unicidad por duplicidad de RIF.

        Debe capturar la violación de integridad y relanzar un ValueError controlado.
        """
        # Arrange
        duplicate_rif = sample_fiscal_profile.rif

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            fiscal_profile_service.create_fiscal_profile(
                entity_name="Otra Empresa",
                use_accrual_method=True,
                fy_start_month=5,
                rif=duplicate_rif,
                code="UNIQUE-CTRL-XYZ",
                taxpayer_type="ORDINARY"
            )
        assert "Error de negocio al procesar la creación del perfil fiscal" in str(exc_info.value)

    def test_create_fiscal_profile_invalid_params_raises_value_error(
        self, fiscal_profile_service: FiscalProfileService
    ) -> None:
        """[ID_EC_002] Verifica fallos ante parámetros obligatorios vacíos.

        Provoca un ValidationError o IntegrityError y asegura la conversión a ValueError.
        """
        # Arrange
        invalid_rif = ""  # Forzar error de validación o restricción de longitud

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            fiscal_profile_service.create_fiscal_profile(
                entity_name="Empresa Fallida",
                use_accrual_method=True,
                fy_start_month=1,
                rif=invalid_rif,
                code="",  # Código vacío que colisionará o fallará
                taxpayer_type="ORDINARY"
            )
        assert "Error de negocio al procesar la creación del perfil fiscal" in str(exc_info.value)

    def test_update_fiscal_profile_duplicate_rif_raises_value_error(
        self,
        fiscal_profile_service: FiscalProfileService,
        sample_fiscal_profile: FiscalProfile,
        admin_user: User
    ) -> None:
        """[ID_EC_003] Valida colisiones de unicidad en la actualización parcial.

        Provoca un error de integridad al duplicar el RIF de otra empresa activa.
        """
        # Arrange
        another_profile = FiscalProfile.create_profile(
            admin=admin_user,
            entity_name="Segunda Empresa",
            use_accrual_method=True,
            fy_start_month=2,
            rif="J-99999999-9",
            code="CTRL-999",
            taxpayer_type="ORDINARY"
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            fiscal_profile_service.update_fiscal_profile(
                fiscal_profile=sample_fiscal_profile,
                rif=another_profile.rif  # Provoca la colisión
            )
        assert "Error de negocio al actualizar el perfil fiscal" in str(exc_info.value)

    def test_update_fiscal_profile_missing_entity_safely_bypasses(
        self, fiscal_profile_service: FiscalProfileService, admin_user: User
    ) -> None:
        """[ID_EC_004] Verifica robustez cuando el objeto carece de entidad.

        Evita excepciones de atributo nulo si `entity` es None en el modelo.
        """
        # Arrange
        profile_no_entity = FiscalProfile.objects.create(
            entity=None,
            name="Sin Entidad S.A.",
            code="CTRL-NO-ENTITY",
            rif="J-00000000-1",
            taxpayer_type="ORDINARY"
        )

        # Act
        updated_profile = fiscal_profile_service.update_fiscal_profile(
            fiscal_profile=profile_no_entity,
            entity_name="Intento de cambio de entidad omitido",
            code="CTRL-NO-ENTITY-MOD"
        )

        # Assert
        assert updated_profile.entity is None
        assert updated_profile.code == "CTRL-NO-ENTITY-MOD"

    def test_update_fiscal_profile_atomic_rollback_on_profile_save_failure(
        self,
        fiscal_profile_service: FiscalProfileService,
        sample_fiscal_profile: FiscalProfile,
        admin_user: User
    ) -> None:
        """[ID_EC_005] Asegura la consistencia atómica mediante reversión automática.

        Falla en el guardado final del perfil fiscal y revierte los cambios hechos a la entidad.
        """
        # Arrange
        another_profile = FiscalProfile.create_profile(
            admin=admin_user,
            entity_name="Empresa Tercera",
            use_accrual_method=True,
            fy_start_month=3,
            rif="J-88888888-8",
            code="CTRL-888",
            taxpayer_type="ORDINARY"
        )
        
        original_entity_name = sample_fiscal_profile.entity.name
        new_entity_name = "Nombre Temporal Atómico"

        # Act & Assert
        # Enviamos un nombre válido de entidad (ejecuta entity.save() con éxito)
        # pero forzamos un IntegrityError al asignar un RIF duplicado en el perfil.
        with pytest.raises(ValueError):
            fiscal_profile_service.update_fiscal_profile(
                fiscal_profile=sample_fiscal_profile,
                entity_name=new_entity_name,
                rif=another_profile.rif
            )

        # Recargamos de la base de datos para validar que ocurrió el Rollback
        sample_fiscal_profile.entity.refresh_from_db()
        assert sample_fiscal_profile.entity.name == original_entity_name
        assert sample_fiscal_profile.entity.name != new_entity_name