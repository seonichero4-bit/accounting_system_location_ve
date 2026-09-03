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
    """Instancia el usuario administrador requerido para la creación de la entidad[cite: 3]."""
    return User.objects.create_superuser(
        username="admin_test",
        email="admin@test.com",
        password="password123"
    )

@pytest.fixture
def fiscal_profile(db, admin_user: User) -> FiscalProfile:
    """Crea el perfil fiscal multi-tenant mediante el servicio FiscalProfileService[cite: 3]."""
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
    """Crea un cliente regular válido que cumple con las restricciones fiscales[cite: 4]."""
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
    """Crea un cliente específico requerido para las transacciones de anulación[cite: 4]."""
    return Customer.objects.create(
        fiscal_profile=fiscal_profile,
        rif="J000000000",
        name="ANULADO",
        fiscal_address="N/A",
        phone_number="00000000000",
        taxpayer_type=Customer.TaxpayerType.NON_TAXPAYER
    )

@pytest.fixture
def base_sales_record(fiscal_profile: FiscalProfile, standard_customer: Customer) -> SalesRecord:
    """
    Instancia en memoria (sin persistir) de un registro de venta interna válido.
    Sirve como base de mutación para los distintos escenarios de prueba unitaria.
    """
    return SalesRecord(
        fiscal_profile=fiscal_profile,
        client=standard_customer,
        document_type="INVOICE",
        sale_type="INTERNAL",
        transaction_type="01_REGISTER",
        record_status="PRELIMINARY",
        document_date=timezone.now().date(),
        control_number="00-000001",
        invoice_number="00000100",
        total_sales_inc_vat=Decimal("116.00"),
        exempt_internal_sales=Decimal("0.00"),
        exonerated_internal_sales=Decimal("0.00"),
        non_subject_internal_sales=Decimal("0.00"),
        general_tax_base_16=Decimal("100.00"),
        general_tax_debit_16=Decimal("16.00"),
        reduced_tax_base_8=Decimal("0.00"),
        reduced_tax_debit_8=Decimal("0.00"),
        additional_tax_base_31=Decimal("0.00"),
        additional_tax_debit_31=Decimal("0.00"),
        igtf_tax_base=Decimal("0.00"),
        igtf_tax_amount=Decimal("0.00"),
        fob_export_value=Decimal("0.00"),
        affected_invoice=None,
        fiscal_printer_number="",
        z_report_number=""
    )