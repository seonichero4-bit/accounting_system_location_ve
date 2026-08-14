"""Módulo de configuración de fixtures de Pytest para la suite de integración.

Extiende la configuración base con objetos reutilizables adicionales
para simular escenarios de facturación y comprobantes de retención ISLR,
garantizando el aislamiento y repetibilidad de las pruebas.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client, RequestFactory

from data_access.models.supplier import LocalSupplier
from data_access.models.base import FiscalProfile
from data_access.models.fiscalperiod import FiscalPeriod
from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.islr_withholding import IslrWithholdingCertificate


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
def fiscal_period(fiscal_profile: FiscalProfile) -> date:
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
def logged_client(admin_user: User, fiscal_profile: FiscalProfile) -> Client:
    """Retorna un cliente de pruebas de Django autenticado con el usuario admin."""
    client = Client()
    client.force_login(admin_user)

    # Inyectar la clave de sesión que el middleware utiliza para resolver request.fiscal_profile
    session = client.session
    session['active_fiscal_profile_id'] = fiscal_profile.pk
    session.save()

    return client


@pytest.fixture
def preliminary_invoice(
    fiscal_profile: FiscalProfile, supplier: LocalSupplier
) -> PurchaseLedgerInvoice:
    """Provee una factura de compra en estado PRELIMINARY para vinculación de ISLR."""
    return PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile,
        supplier=supplier,
        number="INV-100",
        invoice_control="CTRL-100",
        document_type="INVOICE",
        purchase_type="INTERNAL",
        date=date(2026, 8, 1),
        taxable_base=Decimal("100.00"),
        vat_amount=Decimal("16.00"),
        total_purchase=Decimal("116.00"),
        status="PRELIMINARY"
    )


@pytest.fixture
def secondary_preliminary_invoice(
    fiscal_profile: FiscalProfile, supplier: LocalSupplier
) -> PurchaseLedgerInvoice:
    """Provee una segunda factura de compra para probar restricciones OneToOne."""
    return PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile,
        supplier=supplier,
        number="INV-101",
        invoice_control="CTRL-101",
        document_type="INVOICE",
        purchase_type="INTERNAL",
        date=date(2026, 8, 5),
        taxable_base=Decimal("200.00"),
        vat_amount=Decimal("32.00"),
        total_purchase=Decimal("232.00"),
        status="PRELIMINARY"
    )


@pytest.fixture
def processed_islr_certificate(
    preliminary_invoice: PurchaseLedgerInvoice, fiscal_profile: FiscalProfile
) -> IslrWithholdingCertificate:
    """Provee un comprobante de retención de ISLR en estado PROCESSED."""
    # Se ajusta la factura a estado compatible si la lógica lo requiriese, 
    # pero el test asume validación de ciclo de vida del propio comprobante.
    certificate = IslrWithholdingCertificate(
        purchase_invoice=preliminary_invoice,
        document_number="2026080001",
        application_date=date(2026, 8, 10),
        fiscal_profile=fiscal_profile,
        concepts_payment_pjd=1,
        islr_withheld_amount=Decimal("0.00"),
        subtracting=Decimal("0.00"),
        status=IslrWithholdingCertificate.CertificateStatus.PROCESSED
    )
    # Se omite clean() para forzar el estado PROCESSED directo en base de datos
    certificate.save()
    return certificate