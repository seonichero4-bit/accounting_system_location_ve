"""Suite de pruebas para los métodos de consulta y creación de proveedores.

Verifica la lógica de negocio y el aislamiento de datos (multi-tenant) expuesta
en el modelo base FiscalProfile. Implementa el patrón Arrange-Act-Assert.
"""

import pytest
from django.db import IntegrityError
from data_access.models.base import FiscalProfile
from data_access.models.supplier import LocalSupplier


@pytest.mark.django_db
@pytest.mark.unit
class TestFiscalProfileGetSupplier:
    """Pruebas estructuradas para el método get_supplier_by_rif."""

    def test_get_supplier_by_rif_happy_path(
        self, tenant_a_profile: FiscalProfile, tenant_a_supplier: LocalSupplier
    ) -> None:   
        """Escenario Normal: El RIF existe en el perfil fiscal consultado."""
        # Arrange (Estado inyectado mediante los fixtures de conftest.py)

        # Act
        result = tenant_a_profile.get_supplier_by_rif(rif=tenant_a_supplier.rif)

        # Assert
        assert result is not None
        assert result.id == tenant_a_supplier.id
        assert result.rif == tenant_a_supplier.rif

    def test_get_supplier_by_rif_not_found(self, tenant_a_profile: FiscalProfile) -> None:
        """Caso Borde: El RIF no existe en la base de datos."""
        # Arrange
        non_existent_rif = "J-99999999-9"

        # Act
        result = tenant_a_profile.get_supplier_by_rif(rif=non_existent_rif)

        # Assert
        assert result is None

    def test_get_supplier_by_rif_tenant_isolation(
        self, tenant_b_profile: FiscalProfile, tenant_a_supplier: LocalSupplier
    ) -> None:
        """Caso Borde: Fuga de datos (Multi-tenant validation)."""
        # Arrange
        # tenant_a_supplier le pertenece estructuralmente al Inquilino A.
        target_rif = tenant_a_supplier.rif

        # Act
        result = tenant_b_profile.get_supplier_by_rif(rif=target_rif)

        # Assert
        assert result is None, "El RelatedManager no limitó el scope correctamente."

    @pytest.mark.parametrize("empty_input", ["", None])
    def test_get_supplier_by_rif_empty_inputs(
        self, tenant_a_profile: FiscalProfile, empty_input: str | None
    ) -> None:
        """Caso Borde: Entradas vacías o nulas como argumento RIF."""
        # Arrange (Inyectado por el decorador parametrize)

        # Act
        result = tenant_a_profile.get_supplier_by_rif(rif=empty_input)

        # Assert
        assert result is None


@pytest.mark.django_db
@pytest.mark.unit
class TestFiscalProfileCreateSupplier:
    """Pruebas estructuradas para el método create_supplier."""

    def test_create_supplier_happy_path(self, tenant_a_profile: FiscalProfile) -> None:
        """Escenario Normal: Argumentos válidos delegan correctamente al RelatedManager."""
        # Arrange
        kwargs = {
            "name": "Nuevo Proveedor C.A.",
            "rif": "J-55555555-5",
            "supplier_type": LocalSupplier.SupplierType.WITH_RIF,
        }

        # Act
        supplier = tenant_a_profile.create_supplier(**kwargs)

        # Assert
        assert isinstance(supplier, LocalSupplier)
        assert supplier.pk is not None
        assert supplier.fiscal_profile == tenant_a_profile
        assert supplier.rif == "J-55555555-5"

    def test_create_supplier_duplicate_rif(
        self, tenant_a_profile: FiscalProfile, tenant_a_supplier: LocalSupplier
    ) -> None:
        """Caso Borde: RIF duplicado para el mismo perfil fiscal."""
        # Arrange
        kwargs = {
            "name": "Proveedor Duplicado",
            "rif": tenant_a_supplier.rif,  # Intento de colisión de RIF
            "supplier_type": LocalSupplier.SupplierType.WITH_RIF,
        }

        # Act & Assert
        with pytest.raises(IntegrityError):
            tenant_a_profile.create_supplier(**kwargs)

    def test_create_supplier_missing_required_fields(
        self, tenant_a_profile: FiscalProfile
    ) -> None:
        """Caso Borde: Faltan campos obligatorios en la firma del metodo, error python."""
        # Arrange
        kwargs = {
            "fiscal_profile" : self, 
            "rif": "J-88888888-8",
            # Se omiten explícitamente 'name'.
        }

        # Act & Assert
        with pytest.raises(TypeError):
            tenant_a_profile.create_supplier(**kwargs)

    def test_create_supplier_explicit_fiscal_profile_override(
        self, tenant_a_profile: FiscalProfile, tenant_b_profile: FiscalProfile
    ) -> None:
        """Caso Borde: Intento de vulnerar la relación inversa inyectando otro perfil."""
        # Arrange
        kwargs = {
            "fiscal_profile": tenant_b_profile,  # Inyección maliciosa
            "name": "Proveedor Malicioso",
            "rif": "J-77777777-7",
            "supplier_type": LocalSupplier.SupplierType.WITH_RIF,
        }

        # Act & Assert
        # El RelatedManager de Django protege la relación inversa bloqueando 
        # la asignación de un objeto foráneo diferente a la instancia host.
        with pytest.raises((TypeError, ValueError)):
            tenant_a_profile.create_supplier(**kwargs)