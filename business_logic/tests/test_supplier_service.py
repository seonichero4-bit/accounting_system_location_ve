"""Suite de pruebas unitarias y de persistencia para el servicio SupplierService.

Verifica los flujos de creación transaccional e idempotencia del método
register_or_retrieve_local aplicando de forma estricta la arquitectura AAA.
"""

from typing import Any

import pytest
from django.db import IntegrityError

from business_logic.services.supplier_service import SupplierService
from data_access.models.supplier import LocalSupplier


@pytest.mark.django_db
class TestSupplierServiceRegisterOrRetrieve:
    """Pruebas estructuradas para el método register_or_retrieve_local."""

    def test_register_or_retrieve_local_existing_supplier_hp_001(
        self, supplier_service: SupplierService, existing_supplier: LocalSupplier
    ) -> None:
        """[ID_HP_001] Recuperación exitosa de un proveedor local existente por RIF."""
        # Arrange
        supplier_data = {
            "rif": existing_supplier.rif,
            "name": "Intento de Duplicado de Nombre"
        }

        # Act
        supplier, created = supplier_service.register_or_retrieve_local(supplier_data)

        # Assert
        assert supplier.id == existing_supplier.id
        assert supplier.rif == existing_supplier.rif
        assert created is False

    def test_register_or_retrieve_local_new_supplier_hp_002(
        self, supplier_service: SupplierService
    ) -> None:
        """[ID_HP_002] Registro y creación exitosa de un proveedor si el RIF es nuevo."""
        # Arrange
        supplier_data = {
            "rif": "J-98765432-1",
            "name": "Corporación Inversora Nueva C.A."
        }

        # Act
        supplier, created = supplier_service.register_or_retrieve_local(supplier_data)

        # Assert
        assert isinstance(supplier, LocalSupplier)
        assert supplier.pk is not None
        assert supplier.rif == "J-98765432-1"
        assert created is True

    def test_register_or_retrieve_local_missing_rif_ec_001(
        self, supplier_service: SupplierService
    ) -> None:
        """[ID_EC_001] Aborto del flujo si falta la propiedad requerida 'rif'."""
        # Arrange
        supplier_data = {"name": "Proveedor Sin Campo Clave"}

        # Act & Assert
        with pytest.raises(TypeError) as exc_info:
            supplier_service.register_or_retrieve_local(supplier_data)

        assert "missing 1 required positional argument: 'rif'" in str(exc_info.value)

    @pytest.mark.parametrize("empty_rif", ["", None])
    def test_register_or_retrieve_local_empty_rif_ec_002(
        self, supplier_service: SupplierService, empty_rif: Any
    ) -> None:
        """[ID_EC_002] Denegación del procesamiento si el 'rif' es nulo o vacío."""
        # Arrange
        supplier_data = {
            "rif": empty_rif,
            "name": "Proveedor Operaciones Inválidas"
        }

        # Act & Assert
        with pytest.raises(IntegrityError):
            supplier_service.register_or_retrieve_local(supplier_data)

    def test_register_or_retrieve_local_extra_parameters_ec_003(
        self, supplier_service: SupplierService
    ) -> None:
        """[ID_EC_003] Intercepción de parámetros adicionales o mutaciones no deseadas."""
        # Arrange
        supplier_data = {
            "rif": "J-55555555-5",
            "name": "Proveedor Metadatos Extra",
            "parametro_ruido": "Inyección De Formulario"
        }

        # Act & Assert
        with pytest.raises(TypeError) as exc_info:
            supplier_service.register_or_retrieve_local(supplier_data)

        #assert "'parametro_ruido' is an invalid keyword argument" in str(exc_info.value)

    def test_register_or_retrieve_local_invalid_data_types_ec_004(
        self, supplier_service: SupplierService
    ) -> None:
        """[ID_EC_004] Intercepción de inyección de tipos incorrectos en propiedades."""
        # Arrange
        supplier_data = {
            "rif": "J-77777777-7",
            "name": ["Estructura", "No", "Soportada"]
        }

        # Act & Assert
        with pytest.raises((TypeError, ValueError)):
            print(supplier_service.register_or_retrieve_local(supplier_data))