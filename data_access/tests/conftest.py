"""Configuración global de fixtures para la suite de pruebas (Pytest).

Provee las entidades base contables, usuarios y perfiles fiscales necesarios
para ejecutar las pruebas de aislamiento multi-inquilino (tenant).
"""

from typing import Any
import pytest
from django.contrib.auth import get_user_model
from django_ledger.models import EntityModel
from data_access.models.base import FiscalProfile
from data_access.models.supplier import LocalSupplier

# Resolución dinámica del modelo de usuario configurado en Django (AUTH_USER_MODEL)
User = get_user_model()


@pytest.fixture
def user_tenant_a(db) -> Any:
    """Fixture que provee un usuario administrador validado para el inquilino A."""
    return User.objects.create_user(
        username="admin_tenant_a",
        password="secure_password_123",
        email="admin_a@tenant.com"
    )


@pytest.fixture
def user_tenant_b(db) -> Any:
    """Fixture que provee un usuario administrador validado para el inquilino B."""
    return User.objects.create_user(
        username="admin_tenant_b",
        password="secure_password_123",
        email="admin_b@tenant.com"
    )


@pytest.fixture
def ledger_entity_a(db, user_tenant_a: Any) -> EntityModel:
    """Fixture que provee una entidad base contable única para el inquilino A."""
    return EntityModel.create_entity(
        name=f"Tenant A Ledger Entity",
        admin=user_tenant_a,
        use_accrual_method=True,
        fy_start_month=1
    )

@pytest.fixture
def ledger_entity_b(db, user_tenant_b: Any) -> EntityModel:
    """Fixture que provee una entidad base contable única para el inquilino B."""
    return EntityModel.create_entity(
        name=f"Tenant B Ledger Entity",
        admin=user_tenant_b,
        use_accrual_method=True,
        fy_start_month=1
    )


@pytest.fixture
def tenant_a_profile(db, ledger_entity_a: EntityModel) -> FiscalProfile:
    """Fixture que provee un perfil fiscal activo representativo del Inquilino A."""
    return FiscalProfile.objects.create(
        entity=ledger_entity_a,
        code="TENANT-A",
        name="Empresa A C.A.",
        rif="J-11111111-1",
        taxpayer_type=FiscalProfile.TaxpayerType.ORDINARY,
    )


@pytest.fixture
def tenant_b_profile(db, ledger_entity_b: EntityModel) -> FiscalProfile:
    """Fixture que provee un perfil fiscal activo representativo del Inquilino B."""
    return FiscalProfile.objects.create(
        entity=ledger_entity_b,
        code="TENANT-B",
        name="Empresa B C.A.",
        rif="J-22222222-2",
        taxpayer_type=FiscalProfile.TaxpayerType.ORDINARY,
    )


@pytest.fixture
def tenant_a_supplier(db, tenant_a_profile: FiscalProfile) -> LocalSupplier:
    """Fixture que provee un proveedor local asociado estrictamente al Inquilino A."""
    return LocalSupplier.objects.create(
        fiscal_profile=tenant_a_profile,
        name="Proveedor A1",
        rif="J-33333333-3",
        supplier_type=LocalSupplier.SupplierType.WITH_RIF,
    )