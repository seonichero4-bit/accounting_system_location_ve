"""Módulo de configuración de fixtures de Pytest para la suite de pruebas.

Este archivo contiene las fixtures base predefinidas e integración de
cliente HTTP, perfiles fiscales multi-tenant y payloads para pruebas
de integración de los módulos Customer, Views y Forms.
"""

from datetime import date
from typing import Any, Callable, Dict

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django_ledger.io import roles


from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.base import FiscalProfile
from data_access.models.customer import Customer
from data_access.models.fiscalperiod import FiscalPeriod

# ==============================================================================
# FIXTURES BASE DE AUTENTICACIÓN Y CLIENTE HTTP
# ==============================================================================

@pytest.fixture
def admin_user(db) -> User:
    """Instancia el usuario administrador requerido para la creación de la entidad[cite: 1]."""
    return User.objects.create_superuser(
        username="admin_test",
        email="admin@test.com",
        password="password123"
    )


@pytest.fixture
def authenticated_client(client: Client, admin_user: User, fiscal_profile: FiscalProfile) -> Client:
    """Autentica el cliente HTTP de Django con el usuario administrador en sesión."""
    client.force_login(admin_user)

    # Inyectar la clave de sesión que el middleware utiliza
    session = client.session
    session['active_fiscal_profile_id'] = fiscal_profile.pk
    session.save()
    return client


# ==============================================================================
# FIXTURES BASE DE ENTIDAD Y PERFIL FISCAL (TENANT PRINCIPAL)
# ==============================================================================

@pytest.fixture
def fiscal_profile(db, admin_user: User) -> FiscalProfile:
    """Crea el perfil fiscal multi-tenant mediante el servicio FiscalProfileService[cite: 1]."""
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
    """Crea Periodo fiscal alternativo para perfil fiscal ordinario o formal[cite: 1]."""
    fiscal_period_alt = FiscalPeriod.objects.create(
        start_period=date(2026, 1, 1)
    )
    fiscal_period_alt.save()
    return fiscal_period_alt

@pytest.fixture
def chart_of_accounts(db, fiscal_profile: FiscalProfile) -> Any:
    """Genera el Plan de Cuentas base asociado a la entidad del perfil fiscal[cite: 1]."""
    return fiscal_profile.entity.create_chart_of_accounts(
        coa_name="Plan de Cuentas Matriz",
        assign_as_default=True,
        commit=True
    )


# ==============================================================================
# FIXTURES BASE Y PAYLOADS PARA MODELO CUSTOMER
# ==============================================================================

@pytest.fixture
def customer_accounts(db, fiscal_profile: FiscalProfile, chart_of_accounts: Any) -> Dict[str, Any]:
    """Crea e inyecta cuentas contables opcionales asociadas al Ledger del Tenant[cite: 1].

    Genera custom_accounts_receivable y custom_income_account según requerimientos del CustomerForm[cite: 1].
    """
    receivable_acc = fiscal_profile.entity.create_account(
        coa_model=chart_of_accounts,
        code="11201",
        name="Cuentas por Cobrar Comerciales",
        role=roles.ASSET_CA_RECEIVABLES,
        balance_type="debit",
        active=True
    )
    income_acc = fiscal_profile.entity.create_account(
        coa_model=chart_of_accounts,
        code="41101",
        name="Ventas de Mercancía General",
        role=roles.INCOME_OPERATIONAL,
        balance_type="credit",
        active=True
    )
    return {
        "custom_accounts_receivable": receivable_acc,
        "custom_income_account": income_acc,
    }


@pytest.fixture
def valid_customer_payload(fiscal_profile: FiscalProfile) -> Dict[str, Any]:
    """Estructura de datos base (plantilla mutable de modelo) legalmente válida[cite: 1].

    Cumple con los Artículos 76 al 78 del Regla. LIVA[cite: 1].
    """
    return {
        "fiscal_profile": fiscal_profile,
        "rif": "J123456780",
        "name": "Corporación de Servicios Integrales C.A.",
        "fiscal_address": "Av. Principal con Calle 4, Edificio Centro, Piso 3, Oficina 301",
        "phone_number": "02129998877",
        "taxpayer_type": Customer.TaxpayerType.SPECIAL,
    }


@pytest.fixture
def valid_customer_post_data(customer_accounts: Dict[str, Any]) -> Dict[str, Any]:
    """Payload de datos primitivos serializables para peticiones HTTP POST mediante el Client de Django[cite: 2]."""
    return {
        "rif": "J123456789",
        "name": "Distribuidora Central C.A.",
        "fiscal_address": "Calle 10, Edificio A",
        "phone_number": "02125551234",
        "taxpayer_type": Customer.TaxpayerType.ORDINARY,
        "custom_accounts_receivable": customer_accounts["custom_accounts_receivable"].pk,
        "custom_income_account": customer_accounts["custom_income_account"].pk,
    }


@pytest.fixture
def customer_factory(valid_customer_payload: Dict[str, Any]) -> Callable[..., Customer]:
    """Factory Fixture invocable para instanciar/crear registros del modelo Customer[cite: 1].

    Permite sobreescribir únicamente los atributos requeridos por cada test unitario/integración[cite: 1].
    """
    def _create_customer(commit: bool = False, validate: bool = True, **overrides) -> Customer:
        payload = valid_customer_payload.copy()
        payload.update(overrides)
        customer = Customer(**payload)

        if validate:
            customer.full_clean()

        if commit:
            customer.save()

        return customer

    return _create_customer


@pytest.fixture
def persisted_customer(customer_factory: Callable[..., Customer]) -> Customer:
    """Instancia y persiste un cliente activo del inquilino principal en la Base de Datos[cite: 1]."""
    return customer_factory(commit=True, validate=True, rif="J123456780")


# ==============================================================================
# FIXTURES PARA PRUEBAS DE AISLAMIENTO MULTI-TENANT (SEGUNDO INQUILINO)
# ==============================================================================

@pytest.fixture
def secondary_fiscal_profile(db, admin_user: User) -> FiscalProfile:
    """Instancia un segundo perfil fiscal independiente para validar aislamiento multi-tenant[cite: 2, 3]."""
    service = FiscalProfileService(admin_user=admin_user)
    return service.create_fiscal_profile(
        entity_name="Empresa Secundaria C.A.",
        use_accrual_method=True,
        fy_start_month=1,
        rif="J987654321",
        taxpayer_type="ORDINARY",
        start_period=date(2026, 1, 1)
    )


@pytest.fixture
def secondary_customer_accounts(db, secondary_fiscal_profile: FiscalProfile) -> Dict[str, Any]:
    """Genera cuentas contables asociadas exclusivamente al libro contable del inquilino secundario[cite: 2, 3]."""
    coa = secondary_fiscal_profile.entity.create_chart_of_accounts(
        coa_name="Plan de Cuentas Secundario",
        assign_as_default=True,
        commit=True
    )
    receivable_acc = secondary_fiscal_profile.entity.create_account(
        coa_model=coa,
        code="11209",
        name="Cuentas por Cobrar Ajenas",
        role=roles.ASSET_CA_RECEIVABLES,
        balance_type="debit",
        active=True
    )
    income_acc = secondary_fiscal_profile.entity.create_account(
        coa_model=coa,
        code="41109",
        name="Ventas Ajenas",
        role=roles.INCOME_OPERATIONAL,
        balance_type="credit",
        active=True
    )
    return {
        "custom_accounts_receivable": receivable_acc,
        "custom_income_account": income_acc,
    }


@pytest.fixture
def secondary_customer(customer_factory: Callable[..., Customer], secondary_fiscal_profile: FiscalProfile) -> Customer:
    """Persiste un cliente perteneciente al inquilino secundario para validar errores HTTP 404 en vistas[cite: 2, 3]."""
    return customer_factory(
        commit=True,
        fiscal_profile=secondary_fiscal_profile,
        rif="J987654321"
    )