"""Módulo de configuración de fixtures de Pytest para la suite de pruebas.

Este archivo contiene las fixtures base predefinidas e inyecta dependencias
como usuarios, perfiles fiscales, clientes, facturas de venta, cuentas por cobrar,
así como las fixtures de VatWithHolding, IslrWithHolding y CreditNoteSettlement.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Callable, Dict

import pytest
from django.contrib.auth.models import User

from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.base import FiscalProfile
from data_access.models.customer import Customer
from data_access.models.sales_record import SalesRecord
from data_access.models.account_receivable import AccountReceivable, AccountReceivableStatusChoices
from data_access.models.credit_note_settlement import CreditNoteSettlement


@pytest.fixture
def admin_user(db) -> User:
    """Instancia el usuario administrador requerido para la creación de la entidad."""
    return User.objects.create_superuser(
        username="admin_test",
        email="admin@test.com",
        password="password123"
    )


@pytest.fixture
def fiscal_profile(db, admin_user: User) -> FiscalProfile:
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
def standard_customer(db, fiscal_profile: FiscalProfile) -> Customer:
    """Crea un cliente regular válido que cumple con las restricciones fiscales."""
    return Customer.objects.create(
        fiscal_profile=fiscal_profile,
        rif="J312345678",
        name="Inversiones Andinas C.A.",
        fiscal_address="Avenida Bolívar, Sector Centro, Valera, Estado Trujillo",
        phone_number="02712345678",
        taxpayer_type=Customer.TaxpayerType.ORDINARY
    )


@pytest.fixture
def sales_record(db, fiscal_profile: FiscalProfile, standard_customer: Customer) -> SalesRecord:
    """Crea una factura interna válida (Grupo A) que cumple con la ecuación contable y validaciones fiscales."""
    record = SalesRecord(
        fiscal_profile=fiscal_profile,
        client=standard_customer,
        fiscal_period=date(2026, 1, 1),
        document_date=date(2026, 1, 20),
        document_type=SalesRecord.DocumentType.INVOICE,
        transaction_type=SalesRecord.TransactionType.REGISTER,
        sale_type=SalesRecord.SaleType.INTERNAL,
        record_status=SalesRecord.RecordStatus.PRELIMINARY,
	    sale_category=SalesRecord.SaleCategory.GOODS,
        document_number="00000001",
        control_number="00-00000001",
        # Desglose de importes e impuestos (16% IVA general)
        general_tax_base_16=Decimal("100.00"),
        general_tax_debit_16=Decimal("16.00"),
        exempt_internal_sales=Decimal("0.00"),
        exonerated_internal_sales=Decimal("0.00"),
        non_subject_internal_sales=Decimal("0.00"),
        fob_export_value=Decimal("0.00"),
        reduced_tax_base_8=Decimal("0.00"),
        reduced_tax_debit_8=Decimal("0.00"),
        additional_tax_base_31=Decimal("0.00"),
        additional_tax_debit_31=Decimal("0.00"),
        igtf_tax_base=Decimal("0.00"),
        igtf_tax_amount=Decimal("0.00"),
        # Ecuación contable: 100.00 (base) + 16.00 (débito) = 116.00
        total_sales_inc_vat=Decimal("116.00")
    )
    record.save()
    return record


@pytest.fixture
def credit_note_sales_record(
    db,
    fiscal_profile: FiscalProfile,
    standard_customer: Customer,
    sales_record: SalesRecord
) -> SalesRecord:
    """Crea una Nota de Crédito válida (documento de ajuste del Grupo A) 
    asociada a la factura de venta originaria.
    """
    record = SalesRecord(
        fiscal_profile=fiscal_profile,
        client=standard_customer,
        fiscal_period=sales_record.fiscal_period,
        document_date=sales_record.document_date,
        document_type=SalesRecord.DocumentType.CREDIT_NOTE,
        transaction_type=SalesRecord.TransactionType.ADJUSTMENT,
        sale_type=SalesRecord.SaleType.INTERNAL,
        record_status=SalesRecord.RecordStatus.PRELIMINARY,
	    sale_category=SalesRecord.SaleCategory.GOODS,
        document_number="00000002",
        control_number="00-00000002",
        affected_invoice=sales_record,
        # Desglose de importes e impuestos (16% IVA)
        general_tax_base_16=Decimal("10.00"),
        general_tax_debit_16=Decimal("1.60"),
        exempt_internal_sales=Decimal("0.00"),
        exonerated_internal_sales=Decimal("0.00"),
        non_subject_internal_sales=Decimal("0.00"),
        fob_export_value=Decimal("0.00"),
        reduced_tax_base_8=Decimal("0.00"),
        reduced_tax_debit_8=Decimal("0.00"),
        additional_tax_base_31=Decimal("0.00"),
        additional_tax_debit_31=Decimal("0.00"),
        igtf_tax_base=Decimal("0.00"),
        igtf_tax_amount=Decimal("0.00"),
        # Ecuación contable: 10.00 + 1.60 = 11.60
        total_sales_inc_vat=Decimal("11.60")
    )
    record.full_clean()
    record.save()
    return record


@pytest.fixture
def account_receivable(
    db,
    fiscal_profile: FiscalProfile,
    sales_record: SalesRecord
) -> AccountReceivable:
    """Crea una cuenta por cobrar (AccountReceivable) válida vinculada a la factura de venta originaria."""
    receivable = AccountReceivable(
        fiscal_profile=fiscal_profile,
        sales_record=sales_record,
        fiscal_period=sales_record.fiscal_period,
        status=AccountReceivableStatusChoices.PENDING
    )
    receivable.full_clean()
    receivable.save()
    return receivable


@pytest.fixture
def credit_note_settlement_factory(
    db,
    fiscal_profile: FiscalProfile,
    credit_note_sales_record: SalesRecord
) -> Callable[..., CreditNoteSettlement]:
    """Factory fixture para construir e instanciar entidades 'CreditNoteSettlement'.
    
    Genera una liquidación válida ajustada a la Nota de Crédito por defecto (tipo RETURNS),
    y permite sobreescribir cualquier campo o comportamiento de validación en cada test.
    """
    def _create_settlement(**kwargs) -> CreditNoteSettlement:
        target_sales_record = kwargs.pop("sales_record", credit_note_sales_record)
        target_fiscal_profile = kwargs.pop("fiscal_profile", fiscal_profile)
        should_validate = kwargs.pop("validate", True)

        total_amount = target_sales_record.total_sales_inc_vat or Decimal("0.00")

        defaults: Dict[str, Any] = {
            "fiscal_profile": target_fiscal_profile,
            "sales_record": target_sales_record,
            "settlement_type": CreditNoteSettlement.SettlementType.RETURNS,
            "returned_goods_value": total_amount,
            "reimbursement_in_services": Decimal("0.00"),
            "commercial_discount_amount": Decimal("0.00"),
            "cash_amount": total_amount,
            "bank_transfer_amount": Decimal("0.00"),
            "mobile_payment_amount": Decimal("0.00"),
            "card_pos_amount": Decimal("0.00"),
            "customer_credit_balance_amount": Decimal("0.00"),
            "refunded_amount": total_amount,
            "fiscal_period": target_sales_record.fiscal_period,
            "payment_reference": None,
        }

        defaults.update(kwargs)

        settlement = CreditNoteSettlement(**defaults)

        if should_validate:
            settlement.full_clean()

        settlement.save()
        return settlement

    return _create_settlement


@pytest.fixture
def credit_note_settlement(credit_note_settlement_factory) -> CreditNoteSettlement:
    """Fixture estándar que retorna una instancia válida de CreditNoteSettlement."""
    return credit_note_settlement_factory()