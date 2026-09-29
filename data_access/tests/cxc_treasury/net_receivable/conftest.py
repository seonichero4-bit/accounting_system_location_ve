"""Módulo de configuración de fixtures de Pytest para la suite de pruebas.

Este archivo contiene las fixtures base predefinidas e inyecta dependencias
como usuarios, perfiles fiscales, clientes, facturas de venta, así como las
fixtures de VatWithHolding e IslrWithHolding.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Callable, Dict
import itertools

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.base import FiscalProfile
from data_access.models.customer import Customer
from data_access.models.islr_withholding_sales import IslrWithHolding
from data_access.models.sales_record import SalesRecord
from data_access.models.vat_withholding_sales import VatWithHolding
from data_access.models.account_receivable import AccountReceivable, AccountReceivableStatusChoices
from data_access.models.customer_payment import CustomerPayment, PaymentMethodTypeChoices, CurrencyChoices
from data_access.models.payment_imputation import PaymentImputation
from data_access.models.credit_note_settlement import CreditNoteSettlement

_sales_record_counter = itertools.count(start=1)
_vat_withholding_counter = itertools.count(start=1)

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
def sales_record_factory(db, fiscal_profile: FiscalProfile, standard_customer: Customer) -> Callable:
    def _factory(**kwargs):
        seq = next(_sales_record_counter)
        defaults = {
            "fiscal_profile": fiscal_profile,
            "client": standard_customer,
            "document_date": date(2026, 1, 20),
            "fiscal_period": date(2026, 1, 1),
            "document_type": SalesRecord.DocumentType.INVOICE,
            "document_number": f"{seq:08d}",
            "control_number": f"00-{seq:05d}",
            "transaction_type": SalesRecord.TransactionType.REGISTER,
            "sale_type": SalesRecord.SaleType.INTERNAL,
            "sale_category": SalesRecord.SaleCategory.GOODS,
            "total_sales_inc_vat": Decimal("116.00"),
            "general_tax_base_16": Decimal("100.00"),
            "general_tax_debit_16": Decimal("16.00"),
            "record_status": SalesRecord.RecordStatus.PRELIMINARY,
        }
        defaults.update(kwargs)
        return SalesRecord.objects.create(**defaults)
    
    return _factory

@pytest.fixture
def account_receivable(sales_record_factory) -> AccountReceivable:
    """Fixture auxiliar para obtener la Cuenta por Cobrar base.
    
    Almacena la referencia a la CxC que es instanciada y guardada
    automáticamente en base de datos mediante el trigger del método save()
    del modelo SalesRecord.
    """
    sales_record = sales_record_factory(document_type=SalesRecord.DocumentType.INVOICE)
    return sales_record.account_receivable


@pytest.fixture
def vat_withholding_factory(db, fiscal_profile: FiscalProfile, sales_record_factory: Callable) -> Callable:
    def _factory(**kwargs):
        doc = kwargs.get("document") or sales_record_factory()
        seq = next(_vat_withholding_counter)
        
        defaults = {
            "fiscal_profile": fiscal_profile,
            "client": doc.client,
            "document": doc,
            "voucher_number": f"202601{seq:08d}",
            "issue_date": date(2026, 1, 25),
            "fiscal_period": doc.fiscal_period,
            "client_name": doc.client.name,
            "client_rif": doc.client.rif,
            "document_number": doc.document_number,
            "control_number": doc.control_number,
            "total_amount": doc.total_sales_inc_vat,
            "tax_base": doc.general_tax_base_16,
            "tax_caused": doc.general_tax_debit_16,
            "withheld_amount": (doc.general_tax_debit_16 * Decimal("0.75")).quantize(Decimal("0.01")),
        }
        defaults.update(kwargs)
        return VatWithHolding.objects.create(**defaults)
    
    return _factory


@pytest.fixture
def islr_withholding_factory(db, fiscal_profile: FiscalProfile, sales_record_factory: Callable) -> Callable:
    """Factory para generar retenciones de ISLR."""
    def _factory(**kwargs):
        doc = kwargs.get("document") or sales_record_factory()
        
        base = doc.general_tax_base_16 or Decimal("100.00")
        gross = doc.total_sales_inc_vat or Decimal("116.00")
        percentage = Decimal("2.00")
        subtracting = Decimal("0.00")
        
        # Ecuaciones estandarizadas del modelo[cite: 1]
        withheld = (base * (percentage / Decimal("100.00"))) - subtracting
        
        defaults = {
            "fiscal_profile": fiscal_profile,
            "client": doc.client,
            "document": doc,
            "voucher_number": "ISLR-001",
            "issue_date": date(2026, 1, 25),
            "fiscal_period": doc.fiscal_period,
            "client_name": doc.client.name,
            "client_rif": doc.client.rif,
            "document_number": doc.document_number,
            "control_number": doc.control_number,
            "document_date": doc.document_date,
            "seniat_code": "001",
            "gross_amount": gross,
            "tax_base": base,
            "retention_percentage": percentage,
            "subtracting": subtracting,
            "total_withheld_amount": withheld.quantize(Decimal("0.01")),
            "net_amount_to_pay": (gross - withheld).quantize(Decimal("0.01")),
        }
        defaults.update(kwargs)
        return IslrWithHolding.objects.create(**defaults)
    
    return _factory


@pytest.fixture
def customer_payment_factory(db, fiscal_profile: FiscalProfile, standard_customer: Customer) -> Callable:
    """Factory para ingresos y transacciones financieras en tesorería."""
    def _factory(**kwargs):
        defaults = {
            "fiscal_profile": fiscal_profile,
            "customer": standard_customer,
            "fiscal_period": date(2026, 1, 1),
            "payment_date": date(2026, 1, 25),
            "method_type": PaymentMethodTypeChoices.BANK_TRANSFER,
            "currency": CurrencyChoices.VES,
            "nominal_value": Decimal("100.00"),
            "exchange_rate": Decimal("1.0000"),
            "total_amount": Decimal("100.00"),
            "reference": "REF-ABC1234",
        }
        defaults.update(kwargs)
        return CustomerPayment.objects.create(**defaults)
    
    return _factory


@pytest.fixture
def payment_imputation_factory(db, fiscal_profile: FiscalProfile, customer_payment_factory: Callable, sales_record_factory: Callable) -> Callable:
    """Factory para cruzar pagos contra cuentas por cobrar (CxC)."""
    def _factory(**kwargs):
        payment = kwargs.get("payment") or customer_payment_factory()
        
        # Si no se provee CxC, se crea una factura para aprovechar el trigger automático 
        # que instancia la AccountReceivable asociada al modelo INVOICE[cite: 7].
        account_receivable = kwargs.get("account_receivable")
        if not account_receivable:
            sales_record = sales_record_factory()
            account_receivable = sales_record.account_receivable

        defaults = {
            "fiscal_profile": fiscal_profile,
            "payment": payment,
            "account_receivable": account_receivable,
            "fiscal_period": payment.fiscal_period,
            "imputed_amount": Decimal("50.00"),
        }
        defaults.update(kwargs)
        return PaymentImputation.objects.create(**defaults)
    
    return _factory


@pytest.fixture
def credit_note_settlement_factory(db, fiscal_profile: FiscalProfile, sales_record_factory: Callable) -> Callable:
    """Factory para liquidación operativa y financiera de Notas de Crédito."""
    def _factory(**kwargs):
        sales_record = kwargs.get("sales_record")
        
        # Una Nota de Crédito obligatoriamente debe anidarse sobre un registro previo (affected_invoice)[cite: 7]
        if not sales_record:
            base_invoice = sales_record_factory()
            sales_record = sales_record_factory(
                document_type=SalesRecord.DocumentType.CREDIT_NOTE,
                document_number="NC-000001",
                control_number="00-NC001",
                affected_invoice=base_invoice,
                total_sales_inc_vat=Decimal("50.00"),
                general_tax_base_16=Decimal("43.10"),
                general_tax_debit_16=Decimal("6.90")
            )
            
        defaults = {
            "fiscal_profile": fiscal_profile,
            "sales_record": sales_record,
            "settlement_type": CreditNoteSettlement.SettlementType.RETURNS,
            "fiscal_period": sales_record.fiscal_period,
            # Desglose Operativo predeterminado (debe igualar al total_sales_inc_vat)[cite: 3]
            "returned_goods_value": sales_record.total_sales_inc_vat,
            "reimbursement_in_services": Decimal("0.00"),
            "commercial_discount_amount": Decimal("0.00"),
            # Reembolso Financiero predeterminado[cite: 3]
            "bank_transfer_amount": Decimal("0.00"),
            "mobile_payment_amount": Decimal("0.00"),
            "cash_amount": Decimal("0.00"),
            "card_pos_amount": Decimal("0.00"),
            "customer_credit_balance_amount": sales_record.total_sales_inc_vat,
            "refunded_amount": sales_record.total_sales_inc_vat,
        }
        defaults.update(kwargs)
        return CreditNoteSettlement.objects.create(**defaults)
    
    return _factory