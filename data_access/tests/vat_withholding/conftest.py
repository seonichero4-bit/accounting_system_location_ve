"""Módulo de configuración de fixtures de Pytest para la suite de pruebas.

Este archivo contiene las fixtures base predefinidas para inyectar
dependencias como el usuario administrador, perfiles fiscales, plan
clientes y documentos contables en los tests.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Callable, Dict

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.base import FiscalProfile
from data_access.models.customer import Customer
from data_access.models.sales_record import SalesRecord


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
def build_valid_voucher_data() -> Callable[[SalesRecord], dict]:
    """Fixture de tipo factory para generar datos de comprobantes válidos dinámicamente."""
    
    def _factory(sales_record: SalesRecord) -> dict:
        """Genera un diccionario con datos válidos para inicializar VatWithHolding.

        Args:
            sales_record (SalesRecord): Factura de origen preexistente inyectada.

        Returns:
            dict: Atributos obligatorios y calculados del comprobante.
        """
        tax_caused = (
            sales_record.general_tax_debit_16
            + sales_record.reduced_tax_debit_8
            + sales_record.additional_tax_debit_31
        )
        tax_base = (
            sales_record.general_tax_base_16
            + sales_record.reduced_tax_base_8
            + sales_record.additional_tax_base_31
        )

        withheld_amount = (tax_caused * Decimal("0.75")).quantize(Decimal("0.01"))

        return {
            "fiscal_profile": sales_record.fiscal_profile,
            "client": sales_record.client,
            "document": sales_record,
            "voucher_number": "20260100000001",
            "issue_date": date(2026, 1, 25),
            "fiscal_period": date(2026, 1, 1),
            "client_name": sales_record.client.name,
            "client_rif": sales_record.client.rif,
            "document_number": sales_record.document_number,
            "control_number": sales_record.control_number,
            "total_amount": sales_record.total_sales_inc_vat,
            "tax_base": tax_base,
            "tax_caused": tax_caused,
            "withheld_amount": withheld_amount,
        }
        
    return _factory