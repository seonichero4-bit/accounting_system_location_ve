"""Suite de pruebas de integración para el modelo FiscalProfile.

Valida el comportamiento atómico del método de clase `create_profile` ante flujos
felices y casos de borde críticos estipulados en el plan de pruebas técnico.
"""

from typing import Any, Dict
import pytest

from django.contrib.auth.models import User
from django.db import IntegrityError, OperationalError, DataError
from django_ledger.models import EntityModel
from data_access.models.base import FiscalProfile


@pytest.mark.unit
@pytest.mark.django_db#(transaction=True)
class TestFiscalProfileCreateProfile:
    """Conjunto de pruebas integradas para el método `create_profile` estandar."""

    def test_create_profile_success_minimal_data(
        self, db_admin: User, valid_profile_data: Dict[str, Any]
    ) -> None:
        """[ID_HP_001] Validación del flujo feliz de creación de perfil fiscal.

        Verifica que se persistan de forma correcta y atómica tanto la entidad
        de Django Ledger como el perfil fiscal asociado con los datos mínimos.
        """
        # Arrange
        data = valid_profile_data

        # Act
        profile = FiscalProfile.create_profile(
            admin=db_admin,
            entity_name=data["entity_name"],
            use_accrual_method=data["use_accrual_method"],
            fy_start_month=data["fy_start_month"],
            rif=data["rif"],
            #code=data["code"],
            taxpayer_type=data["taxpayer_type"],
            #nit=data["nit"],
        )

        # Assert
        assert profile.id is not None
        assert profile.rif == data["rif"]
        #assert profile.code == data["code"]
        #assert profile.entity is not None
        assert profile.entity.name == data["entity_name"]
        assert EntityModel.objects.filter(uuid=profile.entity.uuid).exists()

    def test_create_profile_missing_mandatory_params_raises_error(
        self, db_admin: User, valid_profile_data: Dict[str, Any]
    ) -> None:
        """[ID_EC_002] Evaluación de fallos ante envío de parámetros nulos.

        Verifica que la restricción de base de datos impida campos obligatorios
        vacíos o nulos como el RIF o el Código de Control Interno.
        """
        # Arrange
        data = valid_profile_data

        # Act & Assert
        with pytest.raises(IntegrityError):
            FiscalProfile.create_profile(
                admin=db_admin,
                entity_name=data["entity_name"],
                use_accrual_method=data["use_accrual_method"],
                fy_start_month=data["fy_start_month"],
                rif=None,  # Campo obligatorio nulo
               #code=data["code"],
                taxpayer_type=data["taxpayer_type"],
            )

    # def test_create_profile_invalid_data_types_raises_error(
    #     self, db_admin: User, valid_profile_data: Dict[str, Any]
    # ) -> None:
    #     """[ID_EC_003] Inyección de tipos de datos incompatibles.

    #     Valida el comportamiento cuando se suministran tipos que rompen las
    #     expectativas del esquema (ej. un arreglo o diccionario en campos de texto).
    #     """
    #     # Arrange
    #     data = valid_profile_data

    #     # Act & Assert
    #     with pytest.raises((ValueError, TypeError, IntegrityError)):
    #         FiscalProfile.create_profile(
    #             admin=db_admin,
    #             entity_name=data["entity_name"],
    #             use_accrual_method=data["use_accrual_method"],
    #             fy_start_month=data["fy_start_month"],
    #             rif=data["rif"],
    #             code=data["code"],
    #             taxpayer_type={1},  # Tipo inválido
    #         )

    def test_create_profile_character_overflow_raises_data_error(
        self, db_admin: User, valid_profile_data: Dict[str, Any]
    ) -> None:
        """[ID_EC_004] Desbordamiento del límite de caracteres en campos de texto.

        Provoca un fallo de almacenamiento enviando un RIF que supera los
        20 caracteres configurados en el modelo físico de la base de datos.
        """
        # Arrange
        data = valid_profile_data
        overflowed_rif = "J" * 25  # Límite máximo es 20 caracteres

        # Act & Assert
        with pytest.raises((DataError, IntegrityError)):
            FiscalProfile.create_profile(
                admin=db_admin,
                entity_name=data["entity_name"],
                use_accrual_method=data["use_accrual_method"],
                fy_start_month=data["fy_start_month"],
                rif=overflowed_rif,
                #code=data["code"],
                taxpayer_type=data["taxpayer_type"],
            )

    # def test_create_profile_special_characters_stored_as_literals(
    #     self, db_admin: User, valid_profile_data: Dict[str, Any]
    # ) -> None:
    #     """[ID_EC_005] Neutralización e inserción segura de scripts o SQL.

    #     Asegura que el ORM escape los caracteres de forma segura guardándolos
    #     como cadenas literales puras sin causar inyecciones dañinas.
    #     """
    #     # Arrange
    #     data = valid_profile_data
    #     dangerous_string = "<script>alert('XSS')</script>; DROP TABLE fiscal_profile;"

    #     # Act
    #     profile = FiscalProfile.create_profile(
    #         admin=db_admin,
    #         entity_name=dangerous_string,
    #         use_accrual_method=data["use_accrual_method"],
    #         fy_start_month=data["fy_start_month"],
    #         rif="J-99999999-9",
    #         code="SPECIAL-CHAR-CODE",
    #         taxpayer_type=data["taxpayer_type"],
    #     )

    #     # Assert
    #     assert profile.id is not None
    #     assert profile.name == dangerous_string
    #     assert profile.entity.name == dangerous_string

    def test_create_profile_db_disconnection_propagates_exception(
        self, monkeypatch: pytest.MonkeyPatch, db_admin: User, valid_profile_data: Dict[str, Any]
    ) -> None:
        """[ID_EC_006] Simulación de interrupción abrupta del motor de base de datos.

        Utiliza el fixture de pytest `monkeypatch` (evitando librerías de mocking)
        para inyectar un fallo de conexión operativa en el flujo interno,
        asegurando la limpia propagación de la excepción.
        """
        # Arrange
        data = valid_profile_data

        def mock_break_transaction(*args: Any, **kwargs: Any) -> Any:
            raise OperationalError("Can't connect to PostgreSQL server on 'localhost'.")

        # Interceptamos el método de creación de Django Ledger usando el fixture nativo
        monkeypatch.setattr(EntityModel, "create_entity", mock_break_transaction)

        # Act & Assert
        with pytest.raises(OperationalError):
            FiscalProfile.create_profile(
                admin=db_admin,
                entity_name=data["entity_name"],
                use_accrual_method=data["use_accrual_method"],
                fy_start_month=data["fy_start_month"],
                rif=data["rif"],
                #code=data["code"],
                taxpayer_type=data["taxpayer_type"],
            )


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
class TestFiscalProfileCreateProfileTransaction:
    """Conjunto de pruebas integradas para el método `create_profile`, en transaccion."""

    def test_create_profile_orphaned_admin_raises_integrity_error(
        self, valid_profile_data: Dict[str, Any]
    ) -> None:
        """[ID_EC_001] Intento de creación con un administrador no persistido.

        Asegura que el sistema aborte la operación ante violaciones de
        integridad referencial o ausencia de una clave foránea válida de usuario.
        """
        # Arrange
        data = valid_profile_data
        unsaved_admin = User(username="huerfano", id=999999)

        # Act & Assert
        with pytest.raises(IntegrityError):
            FiscalProfile.create_profile(
            admin=unsaved_admin,
            entity_name=data["entity_name"],
            use_accrual_method=data["use_accrual_method"],
            fy_start_month=data["fy_start_month"],
            rif=data["rif"],
            #code=data["code"],
            taxpayer_type=data["taxpayer_type"],
        )
