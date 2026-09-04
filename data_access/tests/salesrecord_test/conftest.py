"""Módulo de configuración de fixtures de Pytest para la suite de pruebas.

Este archivo contiene las fixtures base predefinidas para inyectar
dependencias como el usuario administrador, perfiles fiscales, plan
de cuentas, proveedores, clientes y documentos contables en los tests.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Callable, Dict

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from django_ledger.io import roles
from django_ledger.models import LedgerModel

from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.base import FiscalProfile
# Se asume la ruta de importación de los modelos de dominio
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
def annulled_customer(db, fiscal_profile: FiscalProfile) -> Customer:
    """Crea un cliente específico requerido para las transacciones de anulación."""
    return Customer.objects.create(
        fiscal_profile=fiscal_profile,
        rif="J000000000",
        name="ANULADO",
        fiscal_address="N/A",
        phone_number="00000000000",
        taxpayer_type=Customer.TaxpayerType.NON_TAXPAYER
    )

@pytest.fixture
def group_a_invoice_record(fiscal_profile: FiscalProfile, standard_customer: Customer) -> SalesRecord:
    """
    Instancia en memoria de un registro de venta interna (Grupo A - Factura estándar).
    Cumple con la exclusión de campos de impresora fiscal.
    """
    return SalesRecord(
        fiscal_profile=fiscal_profile,
        client=standard_customer,
        document_type="INVOICE",
        document_number="0001",
        control_number="00-000001",
        sale_type="INTERNAL",
        transaction_type="01_REGISTER",
        record_status="PRELIMINARY",
        document_date=timezone.now().date(),
        total_sales_inc_vat=Decimal("116.00"),
        general_tax_base_16=Decimal("100.00"),
        general_tax_debit_16=Decimal("16.00"),
        exempt_internal_sales=Decimal("0.00"),
        exonerated_internal_sales=Decimal("0.00"),
        non_subject_internal_sales=Decimal("0.00"),
        reduced_tax_base_8=Decimal("0.00"),
        reduced_tax_debit_8=Decimal("0.00"),
        additional_tax_base_31=Decimal("0.00"),
        additional_tax_debit_31=Decimal("0.00"),
        igtf_tax_base=Decimal("0.00"),
        igtf_tax_amount=Decimal("0.00"),
        fob_export_value=Decimal("0.00"),
        # affected_invoice=None,
        # invoice_number=None,
        # last_receipt_number=None,
        # fiscal_printer_number=None,
        # z_report_number=None
    )

@pytest.fixture
def group_b_fiscal_printer_record(fiscal_profile: FiscalProfile, standard_customer: Customer) -> SalesRecord:
    """
    Instancia en memoria de un registro por Impresora Fiscal (Grupo B).
    Cumple con la exclusión de campos de documentación interna.
    """
    return SalesRecord(
        fiscal_profile=fiscal_profile,
        client=standard_customer,
        # document_type=None,
        # document_number=None,
        # control_number=None,
        sale_type="INTERNAL",
        transaction_type="01_REGISTER",
        record_status="PRELIMINARY",
        document_date=timezone.now().date(),
        invoice_number="000100",
        last_receipt_number="000105",
        fiscal_printer_number="Z1F1234567",
        z_report_number="0100",
        total_sales_inc_vat=Decimal("116.00"),
        general_tax_base_16=Decimal("100.00"),
        general_tax_debit_16=Decimal("16.00"),
        exempt_internal_sales=Decimal("0.00"),
        exonerated_internal_sales=Decimal("0.00"),
        non_subject_internal_sales=Decimal("0.00"),
        reduced_tax_base_8=Decimal("0.00"),
        reduced_tax_debit_8=Decimal("0.00"),
        additional_tax_base_31=Decimal("0.00"),
        additional_tax_debit_31=Decimal("0.00"),
        igtf_tax_base=Decimal("0.00"),
        igtf_tax_amount=Decimal("0.00"),
        fob_export_value=Decimal("0.00"),
        affected_invoice=None
    )

@pytest.fixture
def export_sales_record(group_a_invoice_record: SalesRecord) -> SalesRecord:
    """
    Instancia en memoria para operaciones de exportación.
    Construida dinámicamente desde el Grupo A, asegurando que solo haya valor FOB.
    """
    group_a_invoice_record.sale_type = "EXPORT"
    group_a_invoice_record.document_number = "0002"
    group_a_invoice_record.control_number = "00-000002"
    group_a_invoice_record.total_sales_inc_vat = Decimal("500.00")
    group_a_invoice_record.fob_export_value = Decimal("500.00")
    group_a_invoice_record.general_tax_base_16 = Decimal("0.00")
    group_a_invoice_record.general_tax_debit_16 = Decimal("0.00")
    return group_a_invoice_record

@pytest.fixture
def annulled_sales_record(group_a_invoice_record: SalesRecord, annulled_customer: Customer) -> SalesRecord:
    """
    Instancia en memoria para transacciones de tipo anulación.
    Aplica cliente especial y montos en 0.
    """
    group_a_invoice_record.client = annulled_customer
    group_a_invoice_record.transaction_type = "03_ANNULMENT"
    group_a_invoice_record.document_number = "0004"
    group_a_invoice_record.control_number = "00-000004"
    group_a_invoice_record.total_sales_inc_vat = Decimal("0.00")
    group_a_invoice_record.general_tax_base_16 = Decimal("0.00")
    group_a_invoice_record.general_tax_debit_16 = Decimal("0.00")
    return group_a_invoice_record

@pytest.fixture
def persisted_sales_record(db, group_a_invoice_record: SalesRecord) -> SalesRecord:
    """
    Registro guardado en base de datos.
    Permite probar persistencia previa y sirve como 'affected_invoice' para Notas de Crédito.
    """
    group_a_invoice_record.save()
    return group_a_invoice_record