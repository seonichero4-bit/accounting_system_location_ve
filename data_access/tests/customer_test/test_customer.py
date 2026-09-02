"""Suite de pruebas unitarias para validaciones y restricciones del modelo Customer.

Este módulo implementa el plan de pruebas para el componente "2. Validations & Constraints"
especificado en la especificación técnica del modelo Customer, asegurando que las
validaciones a nivel de aplicación (Regex, clean) y las restricciones de la base
de datos (Check Constraints, Unique) operen correctamente.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from data_access.models.customer import Customer


@pytest.mark.django_db
class TestCustomerValidations:
    """Conjunto de pruebas para el modelo Customer siguiendo el patrón AAA."""

    # ==============================================================================
    # HAPPY PATHS (Flujos Felices)
    # ==============================================================================

    def test_ID_HP_001_valid_rif_format(self, customer_factory) -> None:
        """Valida que un RIF con estructura correcta es aceptado sin excepciones."""
        # Arrange
        valid_rif = "J12345678"

        # Act
        customer = customer_factory(commit=False, validate=True, rif=valid_rif)

        # Assert
        assert customer.rif == valid_rif

    def test_ID_HP_002_valid_phone_format(self, customer_factory) -> None:
        """Valida que un teléfono con longitud y formato correctos es aceptado."""
        # Arrange
        valid_phone = "02129998877"

        # Act
        customer = customer_factory(commit=False, validate=True, phone_number=valid_phone)

        # Assert
        assert customer.phone_number == valid_phone

    def test_ID_HP_003_rif_and_taxpayer_type_consistency(self, customer_factory) -> None:
        """Valida consistencia lógica entre el prefijo del RIF y el tipo de contribuyente."""
        # Arrange
        consistent_rif = "J12345678"
        consistent_type = Customer.TaxpayerType.SPECIAL

        # Act
        customer = customer_factory(
            commit=False, 
            validate=True, 
            rif=consistent_rif, 
            taxpayer_type=consistent_type
        )

        # Assert
        assert customer.rif == consistent_rif
        assert customer.taxpayer_type == consistent_type

    def test_ID_HP_004_mandatory_fields_persistence(self, customer_factory) -> None:
        """Valida que el registro se guarda en base de datos si los datos son correctos."""
        # Arrange
        valid_data = {
            "rif": "J123456780",
            "name": "Corporación de Servicios Integrales C.A.",
            "fiscal_address": "Av. Principal",
            "phone_number": "02129998877",
            "taxpayer_type": Customer.TaxpayerType.SPECIAL
        }

        # Act
        customer = customer_factory(commit=True, validate=True, **valid_data)

        # Assert
        assert customer.pk is not None

    # ==============================================================================
    # EDGE CASES (Casos Borde y Manejo de Errores)
    # ==============================================================================

    def test_ID_EC_001_unsupported_rif_prefix(self, customer_factory) -> None:
        """Fuerza el validador Regex ingresando un prefijo RIF no soportado."""
        # Arrange
        invalid_prefix_rif = "Z12345678"

        # Act & Assert
        with pytest.raises(ValidationError):
            customer_factory(commit=False, validate=True, rif=invalid_prefix_rif)

    def test_ID_EC_002_rif_too_short(self, customer_factory) -> None:
        """Fuerza el validador Regex con un RIF por debajo del límite inferior."""
        # Arrange
        short_rif = "J1234567"

        # Act & Assert
        with pytest.raises(ValidationError):
            customer_factory(commit=False, validate=True, rif=short_rif)

    def test_ID_EC_003_rif_too_long(self, customer_factory) -> None:
        """Fuerza el validador Regex con un RIF por encima del límite superior."""
        # Arrange
        long_rif = "V1234567890"

        # Act & Assert
        with pytest.raises(ValidationError):
            customer_factory(commit=False, validate=True, rif=long_rif)

    def test_ID_EC_004_phone_too_short(self, customer_factory) -> None:
        """Fuerza el validador Regex con un número telefónico corto."""
        # Arrange
        short_phone = "123456789"

        # Act & Assert
        with pytest.raises(ValidationError):
            customer_factory(commit=False, validate=True, phone_number=short_phone)

    def test_ID_EC_005_phone_too_long(self, customer_factory) -> None:
        """Fuerza el validador Regex con un número telefónico excesivamente largo."""
        # Arrange
        long_phone = "123456789012"

        # Act & Assert
        with pytest.raises(ValidationError):
            customer_factory(commit=False, validate=True, phone_number=long_phone)

    def test_ID_EC_006_fiscal_inconsistency(self, customer_factory) -> None:
        """Dispara validación en clean() por incoherencia entre RIF y Tipo de Contribuyente."""
        # Arrange
        inconsistent_rif = "V12345678"  # Prefijo natural
        inconsistent_type = Customer.TaxpayerType.SPECIAL  # Tipo no coherente simulado

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            customer_factory(
                commit=False, 
                validate=True, 
                rif=inconsistent_rif, 
                taxpayer_type=inconsistent_type
            )
        
        expected_error_msg = (
            "Inconsistencia tributaria: El prefijo del RIF "
            "no corresponde con el Tipo de Contribuyente seleccionado."
        )
        assert expected_error_msg in exc_info.value.message_dict.get("rif", [])

    def test_ID_EC_007_rif_uniqueness_violation(
        self, persisted_customer: Customer, customer_factory
    ) -> None:
        """Evalúa restricción relacional (UniqueConstraint) frente a duplicidad de RIF."""
        # Arrange
        duplicated_rif = persisted_customer.rif

        # Act & Assert
        with pytest.raises(IntegrityError):
            # commit=True y validate=False para saltar full_clean y golpear la DB
            customer_factory(commit=True, validate=False, rif=duplicated_rif)

    @pytest.mark.parametrize("empty_value", ["", "   "])
    def test_ID_EC_008_mandatory_rif_empty(self, customer_factory, empty_value: str) -> None:
        """Evalúa restricción de DB (CheckConstraint) para evitar un RIF vacío o en blanco."""
        # Arrange & Act & Assert
        with pytest.raises(IntegrityError):
            customer_factory(commit=True, validate=False, rif=empty_value)

    @pytest.mark.parametrize("empty_value", ["", "   "])
    def test_ID_EC_009_mandatory_name_empty(self, customer_factory, empty_value: str) -> None:
        """Fuerza CheckConstraint de la base de datos dejando el nombre en blanco."""
        # Arrange & Act & Assert
        with pytest.raises(IntegrityError):
            customer_factory(commit=True, validate=False, name=empty_value)

    @pytest.mark.parametrize("empty_value", ["", "   "])
    def test_ID_EC_010_mandatory_fiscal_address_empty(
        self, customer_factory, empty_value: str
    ) -> None:
        """Fuerza CheckConstraint de la base de datos dejando la dirección fiscal en blanco."""
        # Arrange & Act & Assert
        with pytest.raises(IntegrityError):
            customer_factory(commit=True, validate=False, fiscal_address=empty_value)

    def test_ID_EC_011_null_values_in_restricted_fields(self, customer_factory) -> None:
        """Evalúa el comportamiento de la DB al inyectar nulos absolutos (None) en campos obligatorios."""
        # Arrange
        null_rif = None

        # Act & Assert
        with pytest.raises(IntegrityError):
            customer_factory(commit=True, validate=False, rif=null_rif)