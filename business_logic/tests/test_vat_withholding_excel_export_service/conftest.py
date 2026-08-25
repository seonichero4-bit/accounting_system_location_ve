"""Módulo de configuración y fixtures base para la suite de pruebas fiscales.

Define la inyección de dependencias y estado inicial de la base de datos para
las pruebas unitarias de la contabilidad y fiscalidad venezolana.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict

import pytest
from django.contrib.auth.models import User
from django_ledger.io import roles

from data_access.models.base import FiscalProfile
from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.supplier import LocalSupplier
from data_access.models.vat_withholding import VatWithholdingCertificate
from business_logic.services.fiscal_profile_service import FiscalProfileService


@pytest.fixture
def admin_user(db: Any) -> User:
    """Genera un usuario administrador de Django estándar."""
    return User.objects.create_superuser(
        username="admin_fiscal",
        email="admin@fiscal.com",
        password="password123"
    )


@pytest.fixture
def fiscal_profile(db: Any, admin_user: User) -> FiscalProfile:
    """Instancia un perfil fiscal con tipo de contribuyente SPECIAL.
    
    Se asigna el 15 del mes como inicio del periodo fiscal para cumplir con 
    la restricción de dominio de contribuyentes especiales (quincenal).
    """
    service = FiscalProfileService(admin_user=admin_user)
    return service.create_fiscal_profile(
        entity_name="Empresa C.A.",
        use_accrual_method=True,
        fy_start_month=1,
        rif="J123456780",
        taxpayer_type="SPECIAL",
        start_period=date(2026, 8, 15)
    )


@pytest.fixture
def chart_of_accounts(db: Any, fiscal_profile: FiscalProfile) -> Any:
    """Genera el Plan de Cuentas base asociado a la entidad del perfil fiscal."""
    return fiscal_profile.entity.create_chart_of_accounts(
        coa_name="Plan de Cuentas Matriz",
        assign_as_default=True,
        commit=True
    )


@pytest.fixture
def setup_affected_account(db: Any, fiscal_profile: FiscalProfile, chart_of_accounts: Any) -> Any:
    """Crea la cuenta contable de inventario requerida para las facturas."""
    affected_account = fiscal_profile.entity.create_account(
        coa_model=chart_of_accounts,
        code="11401",
        name="Inventario de Mercancía Disponible",
        role=roles.ASSET_CA_INVENTORY,
        balance_type="debit",
        active=True
    )
    return affected_account


@pytest.fixture
def local_supplier(db: Any, fiscal_profile: FiscalProfile) -> LocalSupplier:
    """Genera un proveedor local base validado fiscalmente."""
    supplier = LocalSupplier(
        fiscal_profile=fiscal_profile,
        name="Proveedor de Prueba",
        rif="J123456780",
        supplier_type=LocalSupplier.SupplierType.WITH_RIF,
        vat_withholding_percentage=LocalSupplier.VatWithholdingPercentageChoices.SEVENTY_FIVE,
    )
    supplier.full_clean()
    supplier.save()
    return supplier


@pytest.fixture
def purchase_ledger_invoice(
    db: Any, 
    fiscal_profile: FiscalProfile, 
    local_supplier: LocalSupplier, 
    setup_affected_account: Any
) -> PurchaseLedgerInvoice:
    """Crea una factura de compra alineada a un periodo fiscal quincenal."""
    account = setup_affected_account

    invoice = PurchaseLedgerInvoice(
        fiscal_profile=fiscal_profile,
        transaction_type=PurchaseLedgerInvoice.TransactionType.REGISTRO,
        document_type=PurchaseLedgerInvoice.DocumentType.INVOICE,
        number="00004567",
        invoice_control="00-00123",
        supplier=local_supplier,
        affected_account=[{"account_id": str(account.uuid), "amount": 1000.00}],
        date=date(2026, 8, 10),
        fiscal_period=date(2026, 8, 15),
        purchase_type=PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        taxable_base=Decimal("1000.00"),
        vat_percentage=PurchaseLedgerInvoice.VatPercentageChoices.GENERAL.value,
        vat_amount=Decimal("160.00"),
        total_purchase=Decimal("1160.00"),
        status=PurchaseLedgerInvoice.InvoiceStatus.PRELIMINARY,
        invoicecategory=PurchaseLedgerInvoice.InvoiceCategory.INVENTARIO,
    )
    invoice.full_clean()
    invoice.save()
    return invoice


@pytest.fixture
def vat_withholding_certificate(
    db: Any, fiscal_profile: FiscalProfile, purchase_ledger_invoice: PurchaseLedgerInvoice
) -> VatWithholdingCertificate:
    """Genera un comprobante de retención alineado a un periodo fiscal quincenal."""
    certificate = VatWithholdingCertificate(
        fiscal_profile=fiscal_profile,
        purchase_invoice=purchase_ledger_invoice,
        application_date=date(2026, 8, 10),
        fiscal_period=date(2026, 8, 15),
        vat_withholding_percentage=VatWithholdingCertificate.VatWithholdingChoices.SETENTA_Y_CINCO,
        document_number="202608000001",
        status=VatWithholdingCertificate.CertificateStatus.PRELIMINARY
    )
    certificate.full_clean()
    certificate.save()
    return certificate