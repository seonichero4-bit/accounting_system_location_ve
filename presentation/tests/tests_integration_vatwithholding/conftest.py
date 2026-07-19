"""Configuración global de fixtures para pytest en la suite de pruebas fiscales.

Define los componentes comunes, usuarios y relaciones necesarios para simular
el ecosistema transaccional multi-inquilino.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import User
import pytest

from data_access.models.base import FiscalProfile
from data_access.models.purchase_book import PurchaseLedgerInvoice


@pytest.fixture
def admin_user(db: Any) -> User:
    """Fixture que provee un usuario administrador para el EntityModel de Django Ledger."""
    return User.objects.create_superuser(
        username="admin_test",
        password="password123",
        email="admin@test.com"
    )


@pytest.fixture
def fiscal_profile(admin_user: User) -> FiscalProfile:
    """Fixture para la creación de un Perfil Fiscal usando el método create_profile."""
    return FiscalProfile.create_profile(
        admin=admin_user,
        entity_name="Empresa Test S.A.",
        use_accrual_method=True,
        fy_start_month=1,
        rif="V123456789",  # Cumple con Regex de formato venezolano oficial
        taxpayer_type="ORDINARY"
    )


@pytest.fixture
def supplier(fiscal_profile: FiscalProfile) -> Any:
    """Fixture para crear un proveedor local a través de la instancia de perfil fiscal."""
    return fiscal_profile.create_supplier(
        name="Proveedor Local S.A.",
        rif="J987654321"
    )


@pytest.fixture
def purchase_invoice(
    fiscal_profile: FiscalProfile, supplier: Any
) -> PurchaseLedgerInvoice:
    """Fixture que genera una factura de compra preliminar con IVA elegible."""
    return PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile,
        supplier=supplier,
        date=date(2026, 7, 1),
        status="PRELIMINARY",
        vat_amount=Decimal("100.00")
    )