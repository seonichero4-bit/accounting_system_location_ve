"""Módulo de configuración de fixtures de Pytest para la suite de pruebas.

Este archivo contiene las fixtures base predefinidas e inyecta dependencias
como usuarios, perfiles fiscales, clientes, facturas de venta, así como las
fixtures de VatWithHolding e IslrWithHolding.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

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
def vat_withholding(
    db,
    fiscal_profile: FiscalProfile,
    standard_customer: Customer,
    sales_record: SalesRecord
) -> VatWithHolding:
    """Crea un comprobante de retención de IVA válido asociado a una factura activa.
    
    Satisface todas las reglas del método clean():
    - Número de comprobante de 14 dígitos que inicia con AAAAMM (202601).
    - Fecha de emisión posterior o igual a la fecha del documento de venta (2026-01-25 >= 2026-01-20).
    - Porcentaje legal del 75% sobre el impuesto causado (16.00 * 0.75 = 12.00).
    """
    withholding = VatWithHolding(
        fiscal_profile=fiscal_profile,
        voucher_number="20260100000001",
        issue_date=date(2026, 1, 25),
        fiscal_period=date(2026, 1, 1),
        client_name=standard_customer.name,
        client_rif=standard_customer.rif,
        document_number=sales_record.document_number,
        control_number=sales_record.control_number,
        total_amount=Decimal("116.00"),
        tax_base=Decimal("100.00"),
        tax_caused=Decimal("16.00"),
        withheld_amount=Decimal("12.00"),
        client=standard_customer,
        document=sales_record
    )
    withholding.full_clean()
    withholding.save()
    return withholding


@pytest.fixture
def islr_withholding(
    db,
    fiscal_profile: FiscalProfile,
    standard_customer: Customer,
    sales_record: SalesRecord
) -> IslrWithHolding:
    """Crea un comprobante de retención de ISLR válido asociado a una factura activa.

    Satisface todas las reglas del método clean():
    - La base imponible (100.00) no excede el monto bruto (100.00).
    - El cálculo del ISLR retenido: (100.00 * 2.00%) - 0.00 = 2.00.
    - El monto neto a pagar: 100.00 - 2.00 = 98.00.
    """
    withholding = IslrWithHolding(
        fiscal_profile=fiscal_profile,
        voucher_number="20260100000001",
        issue_date=date(2026, 1, 25),
        fiscal_period=date(2026, 1, 1),
        client_name=standard_customer.name,
        client_rif=standard_customer.rif,
        document_number=sales_record.document_number,
        control_number=sales_record.control_number,
        document_date=sales_record.document_date,
        seniat_code="001",
        gross_amount=Decimal("100.00"),
        tax_base=Decimal("100.00"),
        retention_percentage=Decimal("2.00"),
        subtracting=Decimal("0.00"),
        total_withheld_amount=Decimal("2.00"),
        net_amount_to_pay=Decimal("98.00"),
        client=standard_customer,
        document=sales_record
    )
    withholding.full_clean()
    withholding.save()
    return withholding

@pytest.fixture
def account_receivable_factory(db, fiscal_profile, sales_record):
    """
    Factory para generar Cuentas por Cobrar (CxC).
    Por defecto, asocia la CxC al documento de venta base y la marca como PENDING.
    """
    def _factory(**kwargs):
        defaults = {
            "fiscal_profile": fiscal_profile,
            "sales_record": sales_record,
            "fiscal_period": date(2026, 1, 1),
            "status": "PENDING"  # AccountReceivableStatusChoices.PENDING
        }
        defaults.update(kwargs)
        
        receivable = AccountReceivable(**defaults)
        # Se asume que la instanciación principal proviene de SalesRecord, 
        # pero para pruebas unitarias aisladas instanciamos y validamos aquí.
        receivable.full_clean()
        receivable.save()
        return receivable
    
    return _factory


@pytest.fixture
def customer_payment_factory(db, fiscal_profile, standard_customer):
    """
    Factory para generar transacciones únicas de Tesorería (CustomerPayment).
    
    Nota: Debido a la regla de 'Cuadre Financiero Global', el método clean() del modelo
    fallará si se llama antes de asociar las instancias de PaymentImputation. Por lo tanto,
    esta fábrica guarda la instancia sin llamar a full_clean(). La validación debe invocarse
    en el test explícitamente después de crear las imputaciones.
    """
    def _factory(**kwargs):
        defaults = {
            "fiscal_profile": fiscal_profile,
            "customer": standard_customer,
            "fiscal_period": date(2026, 1, 1),
            "payment_date": date(2026, 1, 26),
            "method_type": "BANK_TRANSFER",  # PaymentMethodTypeChoices.BANK_TRANSFER
            "currency": "VES",               # CurrencyChoices.VES
	        "nominal_value": Decimal("50.00"), 
            "exchange_rate": Decimal("1.0000"),
            "total_amount": Decimal("50.00"), # (nominal_value * exchange_rate) Valor harcodeado debido a que la logica de calculo esta implementada en el formulario.
            "reference": "REF-123456"
        }
        defaults.update(kwargs)
        
        # Validaciones de consistencia de tasa de cambio inyectadas por defecto
        if defaults["currency"] != "VES" and defaults["exchange_rate"] <= Decimal("0.0000"):
            defaults["exchange_rate"] = Decimal("36.5000")
            
        payment = CustomerPayment(**defaults)
        payment.save()
        return payment
    
    return _factory


@pytest.fixture
def payment_imputation_factory(db, fiscal_profile, customer_payment_factory, account_receivable_factory):
    """
    Factory para generar Imputaciones de Pago (PaymentImputation).
    Asocia un cobro de tesorería a una cuenta por cobrar específica.
    """
    def _factory(**kwargs):
        # Si no se proveen relaciones, se crean al vuelo utilizando las fábricas base
        payment = kwargs.pop("payment", None) or customer_payment_factory()
        account_receivable = kwargs.pop("account_receivable", None) or account_receivable_factory()
        
        defaults = {
            "fiscal_profile": fiscal_profile,
            "payment": payment,
            "account_receivable": account_receivable,
            "fiscal_period": payment.fiscal_period,
            "imputed_amount": Decimal("50.00")
        }
        defaults.update(kwargs)
        
        imputation = PaymentImputation(**defaults)
        
        # Valida el "Tope Impugnable": el monto a imputar no puede exceder el net_receivable_balance
        imputation.full_clean()
        imputation.save()
        return imputation
    
    return _factory


@pytest.fixture
def integrated_payment_scenario(
    account_receivable_factory, 
    customer_payment_factory, 
    payment_imputation_factory
):
    """
    Fixture utilitaria que construye un escenario de pago completo y cuadrado,
    listo para probar las validaciones integrales (incluyendo el clean() del CustomerPayment).
    """
    # 1. Crear la Cuenta por Cobrar (Saldo origen = 116.00 según sales_record)
    ar = account_receivable_factory()
    
    # 2. Registrar el Pago del Cliente por un abono parcial de 50.00
    payment = customer_payment_factory(total_amount=Decimal("50.00"))
    
    # 3. Generar la imputación que cuadra exactamente con el total_amount
    imputation = payment_imputation_factory(
        payment=payment, 
        account_receivable=ar, 
        imputed_amount=Decimal("50.00")
    )
    
    # 4. Validar el Cuadre Financiero Global de forma segura
    payment.full_clean() 
    
    return {
        "account_receivable": ar,
        "payment": payment,
        "imputation": imputation
    }