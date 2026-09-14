"""Módulo de configuración de fixtures de Pytest para la suite de pruebas.

Este archivo contiene las fixtures base predefinidas e inyecta dependencias
como usuarios, perfiles fiscales, clientes, facturas de venta, así como la
fixture de VatWithHolding y la factory de IslrWithHolding.
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
def second_customer(db, fiscal_profile: FiscalProfile) -> Customer:
    """Crea un segundo cliente regular válido para pruebas de aislamiento y concurrencia."""
    return Customer.objects.create(
        fiscal_profile=fiscal_profile,
        rif="J999999999",
        name="Cliente Secundario C.A.",
        fiscal_address="Caracas, Venezuela",
        phone_number="02129999999",
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
def second_sales_record(db, fiscal_profile: FiscalProfile, second_customer: Customer) -> SalesRecord:
    """Crea un segundo registro de venta independiente asociado al cliente secundario."""
    record = SalesRecord(
        fiscal_profile=fiscal_profile,
        client=second_customer,
        fiscal_period=date(2026, 1, 1),
        document_date=date(2026, 1, 20),
        document_type=SalesRecord.DocumentType.INVOICE,
        transaction_type=SalesRecord.TransactionType.REGISTER,
        sale_type=SalesRecord.SaleType.INTERNAL,
        record_status=SalesRecord.RecordStatus.PRELIMINARY,
        document_number="00000002",
        control_number="00-00000002",
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
        total_sales_inc_vat=Decimal("116.00")
    )
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
def islr_withholding_factory(
    db,
    fiscal_profile: FiscalProfile,
    standard_customer: Customer,
    sales_record: SalesRecord
) -> Callable[..., IslrWithHolding]:
    """Factory flexible para construir instancias de IslrWithHolding.
    
    Permite sobreescribir cualquier atributo mediante **kwargs y controlar opcionalmente
    la persistencia/validación mediante los parámetros de control:
    - `commit=True`: Ejecuta `save()` en base de datos.
    - `validate=True`: Ejecuta `full_clean()` antes del guardado.
    """
    def _create_islr_withholding(
        commit: bool = False,
        validate: bool = False,
        **kwargs: Any
    ) -> IslrWithHolding:
        defaults: Dict[str, Any] = {
            "fiscal_profile": fiscal_profile,
            "voucher_number": "00000001",
            "issue_date": date(2026, 1, 25),
            "fiscal_period": date(2026, 1, 1),
            "client_name": sales_record.client.name,
            "client_rif": sales_record.client.rif,
            "document_number": sales_record.document_number,
            "control_number": sales_record.control_number,
            "document_date": sales_record.document_date,
            "seniat_code": "001",
            "gross_amount": Decimal("1000.00"),
            "tax_base": Decimal("1000.00"),
            "retention_percentage": Decimal("3.00"),
            "subtracting": Decimal("0.00"),
            "total_withheld_amount": Decimal("30.00"),
            "net_amount_to_pay": Decimal("970.00"),
            "client": standard_customer,
            "document": sales_record,
        }
        defaults.update(kwargs)

        instance = IslrWithHolding(**defaults)

        if validate:
            instance.full_clean()

        if commit:
            if validate:
                instance.full_clean()
            instance.save()

        return instance

    return _create_islr_withholding