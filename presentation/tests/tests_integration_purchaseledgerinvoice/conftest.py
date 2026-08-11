"""Módulo de configuración de fixtures de Pytest para la suite de integración.

Proporciona objetos base reutilizables, manejando la creación secuencial
de usuarios, perfiles fiscales y datos complementarios requeridos para 
garantizar un entorno de prueba aislado y repetible.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory

from data_access.models.supplier import LocalSupplier
from data_access.models.base import FiscalProfile
from business_logic.services.fiscal_profile_service import FiscalProfileService


@pytest.fixture
def admin_user() -> User:
    """Crea y retorna un usuario administrador requerido por el sistema."""
    return User.objects.create_user(
        username="test_admin",
        password="testpassword123",
        email="admin@test.com"
    )


@pytest.fixture
def fiscal_profile(admin_user: User) -> FiscalProfile:
    """Crea un perfil fiscal asociado al usuario mediante el servicio de dominio."""
    service = FiscalProfileService(admin_user=admin_user)
    return service.create_fiscal_profile(
        entity_name="Empresa de Pruebas CA",
        use_accrual_method=True,
        fy_start_month=1,
        rif="J123456789",
        taxpayer_type="ORDINARY",
        start_period=date(2026, 1, 1)
    )


@pytest.fixture
def fiscal_period(fiscal_profile: FiscalProfile):
    """Retorna el periodo fiscal inicial del perfil fiscal creado."""
    return fiscal_profile.initial_fiscal_period.start_period


@pytest.fixture
def supplier(fiscal_profile: FiscalProfile) -> LocalSupplier:
    """Crea y retorna un proveedor local válido asociado al perfil fiscal."""
    return LocalSupplier.objects.create(
        fiscal_profile=fiscal_profile,
        name="Proveedor de Pruebas",
        rif="J987654321",
        supplier_type="WITH_RIF",
        vat_withholding_percentage=Decimal("0.00")
    )


@pytest.fixture
def request_factory() -> RequestFactory:
    """Retorna una instancia de RequestFactory para simular peticiones HTTP."""
    return RequestFactory()


@pytest.fixture
def base_invoice_data(supplier: LocalSupplier) -> dict[str, any]:
    """Proporciona un diccionario con los datos base para un formulario de factura válido."""
    return {
        "supplier": supplier.pk,
        "number": "INV-100",
        "invoice_control": "CTRL-100",
        "document_type": "INVOICE",
        "purchase_type": "INTERNAL",
        "date": date.today(),
        "exempt_amount": "0.00",
        "amount_exonerated": "0.00",
        "amount_not_subject": "0.00",
        "amount_without_right_to_credit": "0.00",
        "taxable_base": "100.00",
        "vat_percentage": 1,
        "vat_amount": "16.00",
        "igtf_base": "0.00",
        "igtf_amount": "0.00",
        "total_purchase": "116.00",
    }