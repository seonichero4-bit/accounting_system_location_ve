"""Módulo de configuración de fixtures de Pytest para la suite de pruebas.

Este archivo contiene las fixtures base predefinidas para inyectar
dependencias como el usuario administrador, perfiles fiscales, plan
de cuentas, proveedores, clientes y documentos contables en los tests.
"""

from datetime import date
from typing import Any, Callable, Dict

import pytest
from django.contrib.auth.models import User
from django_ledger.io import roles
from django_ledger.models import LedgerModel

from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.base import FiscalProfile
from data_access.models.customer import Customer
from data_access.models.fiscalperiod import FiscalPeriod
from data_access.models.islr_withholding import IslrWithholdingCertificate
from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.supplier import LocalSupplier
from data_access.models.vat_withholding import VatWithholdingCertificate


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
    """Crea el perfil fiscal multi-tenant mediante el servicio FiscalProfileService[cite: 2]."""
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
    """Crea Periodo fiscal alternativo para perfil fiscal ordinario o formal[cite: 2]."""
    fiscal_period_alt = FiscalPeriod.objects.create(
        start_period=date(2026, 1, 1)
    )
    fiscal_period_alt.save()
    return fiscal_period_alt


# @pytest.fixture
# def ledger_model(db, fiscal_profile: FiscalProfile) -> LedgerModel:
#     """Instancia el Libro Mayor General vía ORM vinculándolo a la entidad[cite: 2]."""
#     ledger = LedgerModel.objects.create(
#         name="Libro Mayor General",
#         entity=fiscal_profile.entity
#     )
#     fiscal_profile.ledger = ledger
#     fiscal_profile.save()
#     return ledger


@pytest.fixture
def chart_of_accounts(db, fiscal_profile: FiscalProfile) -> Any:
    """Genera el Plan de Cuentas base asociado a la entidad del perfil fiscal[cite: 2]."""
    return fiscal_profile.entity.create_chart_of_accounts(
        coa_name="Plan de Cuentas Matriz",
        assign_as_default=True,
        commit=True
    )


# ==============================================================================
# FIXTURES BASE PARA MODELO CUSTOMER
# ==============================================================================

@pytest.fixture
def customer_accounts(db, fiscal_profile: FiscalProfile, chart_of_accounts: Any) -> Dict[str, Any]:
    """Crea e inyecta cuentas contables opcionales asociadas al Ledger del Tenant[cite: 2].

    Genera custom_accounts_receivable y custom_income_account según requerimientos del CustomerForm[cite: 2].
    """
    receivable_acc = fiscal_profile.entity.create_account(
        coa_model=chart_of_accounts,
        code="11201",
        name="Cuentas por Cobrar Comerciales",
        role=roles.ASSET_CA_RECEIVABLE,
        balance_type="debit",
        active=True
    )
    income_acc = fiscal_profile.entity.create_account(
        coa_model=chart_of_accounts,
        code="41101",
        name="Ventas de Mercancía General",
        role=roles.INCOME_REVENUE,
        balance_type="credit",
        active=True
    )
    return {
        "custom_accounts_receivable": receivable_acc,
        "custom_income_account": income_acc,
    }


@pytest.fixture
def valid_customer_payload(fiscal_profile: FiscalProfile) -> Dict[str, Any]:
    """Estructura de datos base (plantilla mutable) legalmente válida[cite: 2].

    Cumple con los Artículos 76 al 78 del Regla. LIVA[cite: 2].
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
def customer_factory(valid_customer_payload: Dict[str, Any]) -> Callable[..., Customer]:
    """Factory Fixture invocable para instanciar/crear registros del modelo Customer[cite: 2].

    Permite sobreescribir únicamente los atributos requeridos por cada test unitario[cite: 2].
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
    """Instancia y persiste un cliente activo en la Base de Datos[cite: 2].

    Utilizado para validar colisiones de unicidad de RIF [ID_EC_007][cite: 2].
    """
    return customer_factory(commit=True, validate=True, rif="J123456780")