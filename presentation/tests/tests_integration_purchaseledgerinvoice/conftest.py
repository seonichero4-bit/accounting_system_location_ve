"""
Configuración global de fixtures para la suite de pruebas del Libro de Compras.

Este archivo define los recursos compartidos, inquilinos (FiscalProfiles), 
proveedores locales y documentos fiscales preliminares o procesados requeridos
para las pruebas de integración de las vistas.
"""

import pytest
from typing import Any
from datetime import date
from decimal import Decimal
from django.test import Client
from django.contrib.auth.models import User

from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.base import FiscalProfile
from data_access.models.supplier import LocalSupplier

@pytest.fixture
def admin_user(db: Any) -> User:
    """Fixture que crea y retorna un usuario administrador estándar.

    Args:
        db (Any): Inyección de la base de datos de pytest-django.

    Returns:
        User: Instancia del usuario con privilegios administrativos.
    """
    return User.objects.create_user(
        username="admin_test",
        email="admin@empresa.com",
        password="securepassword123"
    )

@pytest.fixture
def clean_client():
    """Proporciona una instancia limpia del cliente de pruebas de Django."""
    return Client()


@pytest.fixture
def fiscal_profile_a(db, admin_user):
    """Crea el perfil fiscal del Inquilino A (Tenant Activo)."""
    return FiscalProfile.create_profile(
            admin=admin_user,
            entity_name="Empresa cimineto S.A.",
            use_accrual_method=True,
            fy_start_month=1,
            rif="J123456450",
            taxpayer_type="ORDINARY"
    )


@pytest.fixture
def fiscal_profile_b(db, admin_user):
    """Crea el perfil fiscal del Inquilino B (Tenant Ajeno para Cross-Tenant)."""
    return FiscalProfile.create_profile(
            admin=admin_user,
            entity_name="Empresa Base S.A.",
            use_accrual_method=True,
            fy_start_month=1,
            rif="J123456780",
            taxpayer_type="ORDINARY"
    )


@pytest.fixture
def auth_client_profile_a(clean_client, fiscal_profile_a):
    """Configura el cliente inyectando el Perfil Fiscal A en la sesión activa."""
    session = clean_client.session
    session['fiscal_profile_id'] = fiscal_profile_a.id
    session.save()
    return clean_client


@pytest.fixture
def supplier_a(db, fiscal_profile_a):
    """Crea un proveedor local asociado al Perfil Fiscal A."""
    return LocalSupplier.objects.create(
        fiscal_profile=fiscal_profile_a,
        rif="J-33333333-3",
        name="Proveedor Nacional A, C.A."
    )


@pytest.fixture
def supplier_b(db, fiscal_profile_b):
    """Crea un proveedor local asociado al Perfil Fiscal B."""
    return LocalSupplier.objects.create(
        fiscal_profile=fiscal_profile_b,
        rif="J-44444444-4",
        name="Proveedor Nacional B, C.A."
    )


@pytest.fixture
def invoice_preliminary_a(db, fiscal_profile_a, supplier_a):
    """Genera una factura en estado inicial (PRELIMINARY) para el Perfil A."""
    return PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile_a,
        supplier=supplier_a,
        number="10050",
        invoice_control="00-998822",
        document_type=PurchaseLedgerInvoice.DocumentType.INVOICE,
        purchase_type=PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        status=PurchaseLedgerInvoice.InvoiceStatus.PRELIMINARY,  # Equivalente al estado preliminar del flujo
        date=date(2026, 6, 1),
        application_month_year="06-2026",
        taxable_base=Decimal("500.00"),
        exempt_amount=Decimal("100.00"),
        vat_amount=Decimal("80.00"),
        igtf_amount=Decimal("0.00"),
        subtotal=Decimal("600.00"),
        total_purchase=Decimal("680.00")
    )


@pytest.fixture
def invoice_processed_a(db, fiscal_profile_a, supplier_a):
    """Genera una factura en estado inmutable (PROCESSED) para el Perfil A."""
    return PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile_a,
        supplier=supplier_a,
        number="20060",
        invoice_control="00-998823",
        document_type=PurchaseLedgerInvoice.DocumentType.INVOICE,
        purchase_type=PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        status=PurchaseLedgerInvoice.InvoiceStatus.PROCESSED,
        date=date(2026, 6, 1),
        application_month_year="06-2026",
        taxable_base=Decimal("1000.00"),
        exempt_amount=Decimal("0.00"),
        vat_amount=Decimal("160.00"),
        igtf_amount=Decimal("0.00"),
        subtotal=Decimal("1000.00"),
        total_purchase=Decimal("1160.00")
    )


@pytest.fixture
def invoice_profile_b(db, fiscal_profile_b, supplier_b):
    """Genera una factura perteneciente al Perfil Fiscal B (Inquilino Ajeno)."""
    return PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile_b,
        supplier=supplier_b,
        number="99999",
        invoice_control="00-111111",
        document_type=PurchaseLedgerInvoice.DocumentType.INVOICE,
        purchase_type=PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        status=PurchaseLedgerInvoice.InvoiceStatus.PRELIMINARY,
        date=date(2026, 6, 1),
        application_month_year="06-2026",
        taxable_base=Decimal("200.00"),
        exempt_amount=Decimal("0.00"),
        vat_amount=Decimal("32.00"),
        igtf_amount=Decimal("0.00"),
        subtotal=Decimal("200.00"),
        total_purchase=Decimal("232.00")
    )