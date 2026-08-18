"""Módulo de configuración de fixtures para la suite de pruebas.

Este archivo contiene las fixtures base predefinidas para inyectar
dependencias como el usuario administrador, perfiles fiscales, plan
de cuentas, proveedores y documentos contables en los tests.
"""

import pytest
from datetime import date
from decimal import Decimal
from django.contrib.auth.models import User
from django_ledger.models import LedgerModel
from django_ledger.io import roles

from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.base import FiscalProfile
from data_access.models.fiscalperiod import FiscalPeriod
from data_access.models.supplier import LocalSupplier
from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.vat_withholding import VatWithholdingCertificate
from data_access.models.islr_withholding import IslrWithholdingCertificate

@pytest.fixture
def admin_user(db) -> User:
    """Instancia el usuario administrador requerido para la creación de la entidad."""
    return User.objects.create_superuser(
        username="admin_test",
        email="admin@test.com",
        password="password123"
    )

@pytest.fixture
def fiscal_profile(db, admin_user) -> FiscalProfile:
    """Crea el perfil fiscal multi-tenant mediante el servicio FiscalProfileService."""
    service = FiscalProfileService(admin_user=admin_user)
    return service.create_fiscal_profile(
        entity_name="Empresa de Prueba C.A.",
        use_accrual_method=True,
        fy_start_month=1,
        rif="J123456789",
        taxpayer_type="SPECIAL",
        start_period=date(2026, 1, 15)
    )

@pytest.fixture
def fiscal_period_alternative(db) -> FiscalPeriod:
    """Crea Periodo fiscal alternativo para perfil fiscal ordinario o formal"""
    fiscal_period_alternative = FiscalPeriod.objects.create(
        start_period=date(2026, 1, 1)
    )
    fiscal_period_alternative.save
    return fiscal_period_alternative

@pytest.fixture
def ledger_model(db, fiscal_profile) -> LedgerModel:
    """Instancia el Libro Mayor General vía ORM vinculándolo a la entidad."""
    ledger = LedgerModel.objects.create(
        name="Libro Mayor General",
        entity=fiscal_profile.entity
    )
    fiscal_profile.ledger = ledger
    fiscal_profile.save()
    return ledger

@pytest.fixture
def chart_of_accounts(db, fiscal_profile):
    """Genera el Plan de Cuentas base asociado a la entidad del perfil fiscal."""
    return fiscal_profile.entity.create_chart_of_accounts(
        coa_name="Plan de Cuentas Matriz",
        assign_as_default=True,
        commit=True
    )

@pytest.fixture
def setup_accounts(db, fiscal_profile, chart_of_accounts, ledger_model) -> dict:
    """Instancia las cuentas contables y asigna cuentas de control al perfil fiscal."""
    raw_accounts = [
        {"code": "11401", "name": "Inventario de Mercancía Disponible", "role": roles.ASSET_CA_INVENTORY, "balance_type": "debit"},
        {"code": "11301", "name": "IVA Crédito Fiscal", "role": roles.ASSET_CA_PREPAID, "balance_type": "debit"},
        {"code": "62103", "name": "Gasto por IGTF", "role": roles.EXPENSE_TAXES, "balance_type": "debit"},
        {"code": "21203", "name": "Retenciones de ISLR por Pagar", "role": roles.LIABILITY_CL_TAXES_PAYABLE, "balance_type": "credit"},
        {"code": "21101", "name": "Proveedores Nacionales", "role": roles.LIABILITY_CL_ACC_PAYABLE, "balance_type": "credit"},
        {"code": "21202", "name": "Retenciones de IVA por Pagar", "role": roles.LIABILITY_CL_TAXES_PAYABLE, "balance_type": "credit"},
        {"code": "61203", "name": "Honorarios Profesionales", "role": roles.EXPENSE_OPERATIONAL, "balance_type": "debit"},
        {"code": "61201", "name": "Gastos suministros", "role": roles.EXPENSE_OPERATIONAL, "balance_type": "debit"},
    ]

    created_accounts = {}
    for acc in raw_accounts:
        account_instance = fiscal_profile.entity.create_account(
            coa_model=chart_of_accounts,
            code=acc["code"],
            name=acc["name"],
            role=acc["role"],
            balance_type=acc["balance_type"],
            active=True
        )
        created_accounts[acc["code"]] = account_instance

    fiscal_profile.ledger = ledger_model
    fiscal_profile.inventory_account = created_accounts["11401"]
    fiscal_profile.vat_credit_account = created_accounts["11301"]
    fiscal_profile.igtf_expense_account = created_accounts["62103"]
    fiscal_profile.islr_payable_account = created_accounts["21203"]
    fiscal_profile.cxp_suppliers_account = created_accounts["21101"]
    fiscal_profile.vat_withheld_payable_account = created_accounts["21202"]
    fiscal_profile.save()

    return created_accounts

@pytest.fixture
def local_supplier(db, fiscal_profile) -> LocalSupplier:
    """Instancia un proveedor local vía ORM."""
    return LocalSupplier.objects.create(
        fiscal_profile=fiscal_profile,
        name="Proveedor Servicios Generales S.A.",
        rif="J987654321",
        supplier_type=LocalSupplier.SupplierType.WITH_RIF,
        vat_withholding_percentage=Decimal("75.00")
    )

@pytest.fixture
def purchase_ledger_invoice(db, fiscal_profile, local_supplier, setup_accounts) -> PurchaseLedgerInvoice:
    """Instancia la factura de compra asignando cuentas afectadas válidas."""

    created_accounts = setup_accounts
    account = created_accounts["61203"]
    
    return PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile,
        supplier=local_supplier,
        transaction_type=PurchaseLedgerInvoice.TransactionType.REGISTRO,
        document_type=PurchaseLedgerInvoice.DocumentType.INVOICE,
        number="FAC-2026-001",
        invoice_control="CTRL-001",
        date=date(2026, 8, 15),
        fiscal_period=date(2026, 8, 31),
        taxable_base=Decimal("1000.00"),
        vat_percentage=PurchaseLedgerInvoice.VatPercentageChoices.GENERAL,
        vat_amount=Decimal("160.00"),
        subtotal=Decimal("1000.00"),
        total_purchase=Decimal("1160.00"),
        status=PurchaseLedgerInvoice.InvoiceStatus.PRELIMINARY,
        affected_account=[{"account_id": str(account.uuid), "amount": 1000.00}],
        invoicecategory=PurchaseLedgerInvoice.InvoiceCategory.SERVICIO
    )

@pytest.fixture
def vat_withholding_certificate(db, fiscal_profile, purchase_ledger_invoice) -> VatWithholdingCertificate:
    """Instancia directa del comprobante de retención de IVA vía ORM."""
    return VatWithholdingCertificate.objects.create(
        fiscal_profile=fiscal_profile,
        purchase_invoice=purchase_ledger_invoice,
        application_date=date(2026, 8, 15),
        fiscal_period=date(2026, 8, 31),
        document_number="20260800000001",
        vat_withholding_percentage=VatWithholdingCertificate.VatWithholdingChoices.SETENTA_Y_CINCO,
        status=VatWithholdingCertificate.CertificateStatus.PRELIMINARY
    )

@pytest.fixture
def islr_withholding_certificate(db, fiscal_profile, purchase_ledger_invoice) -> IslrWithholdingCertificate:
    """Instancia directa del comprobante de retención de ISLR vía ORM."""
    return IslrWithholdingCertificate.objects.create(
        fiscal_profile=fiscal_profile,
        purchase_invoice=purchase_ledger_invoice,
        document_number="20260800000002",
        application_date=date(2026, 8, 15),
        fiscal_period=date(2026, 8, 31),
        concepts_payment_pjd=1,
        status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
    )