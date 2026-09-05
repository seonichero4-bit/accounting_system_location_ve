"""Módulo de configuración de fixtures de Pytest para la suite de pruebas.

Este archivo contiene las fixtures base predefinidas para inyectar
dependencias y simular escenarios de pruebas unitarias y de integración
para el modelo SalesRecord, incluyendo aislamiento multi-inquilino.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

# Se asume la ruta de importación de los modelos de dominio
from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.base import FiscalProfile, FiscalPeriod
from data_access.models.customer import Customer
from data_access.models.sales_record import SalesRecord


# ==============================================================================
# FIXTURES BASE Y DE DOMINIO
# ==============================================================================

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
def group_a_invoice_record(fiscal_profile: FiscalProfile, standard_customer: Customer, active_fiscal_period: FiscalPeriod) -> SalesRecord:
    """Instancia en memoria de un registro de venta interna (Grupo A - Factura estándar)."""
    return SalesRecord(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 1, 15),
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
        affected_invoice=None,
        invoice_number=None,
        last_receipt_number=None,
        fiscal_printer_number=None,
        z_report_number=None
    )


@pytest.fixture
def persisted_sales_record(db, group_a_invoice_record: SalesRecord) -> SalesRecord:
    """Registro guardado en base de datos. Sirve como 'affected_invoice'."""
    group_a_invoice_record.save()
    return group_a_invoice_record


# ==============================================================================
# FIXTURES DE INTEGRACIÓN Y ENTORNO HTTP
# ==============================================================================

@pytest.fixture
def authenticated_client(client: Client, admin_user: User, fiscal_profile: FiscalProfile, 
    active_fiscal_period: FiscalPeriod) -> Client:
    """Cliente HTTP autenticado para ejecutar peticiones GET/POST."""
    client.force_login(admin_user)

    # Inyectar la clave de sesión que el middleware utiliza
    session = client.session
    session['active_fiscal_profile_id'] = fiscal_profile.pk
    session['active_fiscal_period_id'] = active_fiscal_period.pk
    session.save()

    return client

@pytest.fixture
def active_fiscal_period(db, fiscal_profile: FiscalProfile) -> FiscalPeriod:
    """Período fiscal activo requerido para inyección en vistas de creación."""
    return  fiscal_profile.initial_fiscal_period

@pytest.fixture
def valid_sales_record_payload(standard_customer: Customer) -> Dict[str, Any]:
    """Carga útil (payload) válida para simular envíos POST de formularios."""
    return {
        "client": standard_customer.id,
        "document_type": "INVOICE",
        "document_number": "0005",
        "control_number": "00-000005",
        "sale_type": "INTERNAL",
        "transaction_type": "01_REGISTER",
        "document_date": timezone.now().date().isoformat(),
        "total_sales_inc_vat": "232.00",
        "general_tax_base_16": "200.00",
        "general_tax_debit_16": "32.00",
        "exempt_internal_sales": "0.00",
        "exonerated_internal_sales": "0.00",
        "non_subject_internal_sales": "0.00",
        "reduced_tax_base_8": "0.00",
        "reduced_tax_debit_8": "0.00",
        "additional_tax_base_31": "0.00",
        "additional_tax_debit_31": "0.00",
        "igtf_tax_base": "0.00",
        "igtf_tax_amount": "0.00",
        "fob_export_value": "0.00"
    }


# ==============================================================================
# FIXTURES PARA AISLAMIENTO MULTI-INQUILINO Y ESTADOS BORDES
# ==============================================================================

@pytest.fixture
def other_tenant_user(db) -> User:
    """Usuario administrador perteneciente a un inquilino secundario."""
    return User.objects.create_superuser(
        username="other_admin",
        email="other@test.com",
        password="password123"
    )

@pytest.fixture
def other_tenant_profile(db, other_tenant_user: User) -> FiscalProfile:
    """Perfil fiscal de un segundo inquilino para pruebas de aislamiento cruzado."""
    service = FiscalProfileService(admin_user=other_tenant_user)
    return service.create_fiscal_profile(
        entity_name="Otra Empresa C.A.",
        use_accrual_method=True,
        fy_start_month=1,
        rif="J987654321",
        taxpayer_type="ORDINARY",
        start_period=date(2026, 1, 1)
    )

@pytest.fixture
def other_tenant_customer(db, other_tenant_profile: FiscalProfile) -> Customer:
    """Cliente vinculado al inquilino secundario."""
    return Customer.objects.create(
        fiscal_profile=other_tenant_profile,
        rif="J555555555",
        name="Cliente de Otro Inquilino C.A.",
        fiscal_address="Avenida Principal, Otra Ciudad",
        phone_number="04140000000",
        taxpayer_type=Customer.TaxpayerType.ORDINARY
    )

@pytest.fixture
def other_tenant_sales_record(
    db, 
    other_tenant_profile: FiscalProfile, 
    other_tenant_customer: Customer, 
    group_a_invoice_record: SalesRecord
) -> SalesRecord:
    """Registro de venta persistido perteneciente al inquilino secundario."""
    group_a_invoice_record.pk = None
    group_a_invoice_record.fiscal_profile = other_tenant_profile
    group_a_invoice_record.client = other_tenant_customer
    group_a_invoice_record.save()
    return group_a_invoice_record

@pytest.fixture
def processed_sales_record(db, group_a_invoice_record: SalesRecord) -> SalesRecord:
    """Registro de venta guardado con estatus inmutable (procesado)."""
    group_a_invoice_record.record_status = "PROCESSED"
    group_a_invoice_record.save()
    return group_a_invoice_record