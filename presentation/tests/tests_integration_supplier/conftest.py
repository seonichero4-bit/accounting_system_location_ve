"""Configuración de fixtures para la suite de pruebas de la capa de presentación.

Provee perfiles fiscales, inquilinos y proveedores locales preconfigurados
para garantizar un entorno de pruebas aislado y determinista.
"""

from typing import Any
import pytest
from django.contrib.auth import get_user_model
from django_ledger.models import EntityModel
from data_access.models.base import FiscalProfile
from data_access.models.supplier import LocalSupplier

User = get_user_model()


@pytest.fixture
def test_user_a(db: Any) -> Any:
    """Crea y retorna un usuario administrador para el Inquilino A."""
    return User.objects.create_user(
        username="admin_tenant_a", password="secure_password_123"
    )


@pytest.fixture
def test_user_b(db: Any) -> Any:
    """Crea y retorna un usuario administrador para el Inquilino B."""
    return User.objects.create_user(
        username="admin_tenant_b", password="secure_password_123"
    )


@pytest.fixture
def ledger_entity_a(db: Any, test_user_a: Any) -> EntityModel:
    """Crea la entidad contable base para el Inquilino A."""
    return EntityModel.create_entity(
        name="Tenant A Ledger Entity",
        admin=test_user_a,
        use_accrual_method=True,
        fy_start_month=1,
    )


@pytest.fixture
def ledger_entity_b(db: Any, test_user_b: Any) -> EntityModel:
    """Crea la entidad contable base para el Inquilino B."""
    return EntityModel.create_entity(
        name="Tenant B Ledger Entity",
        admin=test_user_b,
        use_accrual_method=True,
        fy_start_month=1,
    )


@pytest.fixture
def tenant_a_profile(db: Any, ledger_entity_a: EntityModel) -> FiscalProfile:
    """Crea y retorna el perfil fiscal asociado al Inquilino A."""
    return FiscalProfile.objects.create(
        entity=ledger_entity_a,
        name="Empresa A C.A.",
        rif="J111111111",
        taxpayer_type=FiscalProfile.TaxpayerType.ORDINARY,
    )


@pytest.fixture
def tenant_b_profile(db: Any, ledger_entity_b: EntityModel) -> FiscalProfile:
    """Crea y retorna el perfil fiscal asociado al Inquilino B."""
    return FiscalProfile.objects.create(
        entity=ledger_entity_b,
        name="Empresa B C.A.",
        rif="J222222222",
        taxpayer_type=FiscalProfile.TaxpayerType.ORDINARY,
    )


@pytest.fixture
def tenant_a_suppliers(db: Any, tenant_a_profile: FiscalProfile) -> list[LocalSupplier]:
    """Crea tres proveedores de prueba vinculados estrictamente al Inquilino A."""
    return [
        tenant_a_profile.create_supplier(
            name="Proveedor A1 C.A.",
            rif="J333333333",
            supplier_type=LocalSupplier.SupplierType.WITH_RIF,
        ),
        tenant_a_profile.create_supplier(
            name="Proveedor A2 C.A.",
            rif="J444444444",
            supplier_type=LocalSupplier.SupplierType.WITH_RIF,
        ),
        tenant_a_profile.create_supplier(
            name="Proveedor A3 C.A.",
            rif="J555555555",
            supplier_type=LocalSupplier.SupplierType.WITH_RIF,
        ),
    ]


@pytest.fixture
def tenant_b_supplier(db: Any, tenant_b_profile: FiscalProfile) -> LocalSupplier:
    """Crea un proveedor de prueba vinculado estrictamente al Inquilino B."""
    return tenant_b_profile.create_supplier(
        name="Proveedor B1 C.A.",
        rif="J666666666",
        supplier_type=LocalSupplier.SupplierType.WITH_RIF,
    )