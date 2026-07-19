"""Configuración global de fixtures para la suite de pruebas de retenciones de ISLR.

Define los entornos, usuarios, perfiles fiscales multi-inquilino, proveedores locales
y facturas de compra requeridas para la ejecución limpia y aislada de las pruebas.
"""

from typing import Any
from datetime import date
from decimal import Decimal
from typing import Generator
import pytest
from django.contrib.auth.models import User
from django.test import Client

from data_access.models.base import FiscalProfile
from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.supplier import LocalSupplier


@pytest.fixture(scope="function")
def client() -> Client:
    """Proporciona una instancia limpia del cliente de pruebas de Django.

    Returns:
        Client: El cliente HTTP nativo de Django para interactuar con las vistas.
    """
    return Client()


@pytest.fixture(scope="function")
def admin_user(db: Any) -> User:
    """Crea un usuario administrador base requerido por las entidades contables.

    Args:
        db: Componente de persistencia en base de datos de pytest-django.

    Returns:
        User: Instancia del usuario con privilegios administrativos.
    """
    return User.objects.create_superuser(
        username="admin_fiscal",
        email="admin@fiscal.com",
        password="secret_password"
    )


@pytest.fixture(scope="function")
def tenant_profile(admin_user: User) -> FiscalProfile:
    """Crea el perfil fiscal primario utilizando el método oficial create_profile.

    Args:
        admin_user (User): Administrador asociado a la entidad contable.

    Returns:
        FiscalProfile: Instancia del perfil fiscal del primer inquilino.
    """
    profile = FiscalProfile.create_profile(
        admin=admin_user,
        entity_name="Empresa Local Primaria C.A.",
        use_accrual_method=True,
        fy_start_month=1,
        rif="J123456789",
        taxpayer_type="ORDINARY"
    )
    # Configuración explícita de la Unidad Tributaria requerida para cálculos normativos
    profile.ut = Decimal("150.00")
    profile.save()
    return profile


@pytest.fixture(scope="function")
def secondary_tenant_profile(admin_user: User) -> FiscalProfile:
    """Crea un segundo perfil fiscal independiente para pruebas de aislamiento de datos.

    Args:
        admin_user (User): Administrador asociado a la entidad contable.

    Returns:
        FiscalProfile: Instancia del perfil fiscal del segundo inquilino.
    """
    profile = FiscalProfile.create_profile(
        admin=admin_user,
        entity_name="Corporación Foránea Inquilino Dos S.A.",
        use_accrual_method=True,
        fy_start_month=1,
        rif="J987654321",
        taxpayer_type="SPECIAL"
    )
    profile.ut = Decimal("150.00")
    profile.save()
    return profile


@pytest.fixture(scope="function")
def local_supplier(tenant_profile: FiscalProfile) -> LocalSupplier:
    """Crea un proveedor local asociado al perfil primario mediante create_supplier.

    Args:
        tenant_profile (FiscalProfile): Perfil fiscal del inquilino primario.

    Returns:
        LocalSupplier: Instancia del proveedor local asignado.
    """
    return tenant_profile.create_supplier(
        name="Inversiones Médicas del Centro, C.A.",
        rif="V112223330",
    )


@pytest.fixture(scope="function")
def secondary_local_supplier(secondary_tenant_profile: FiscalProfile) -> LocalSupplier:
    """Crea un proveedor local asociado al segundo perfil fiscal independiente.

    Args:
        secondary_tenant_profile (FiscalProfile): Perfil fiscal del segundo inquilino.

    Returns:
        LocalSupplier: Instancia del proveedor local del inquilino secundario.
    """
    return secondary_tenant_profile.create_supplier(
        name="Suministros Globales del Segundo Tenant",
        rif="V223334440"
    )


@pytest.fixture(scope="function")
def preliminary_purchase_invoice(
    tenant_profile: FiscalProfile, 
    local_supplier: LocalSupplier
) -> PurchaseLedgerInvoice:
    """Instancia y persiste una factura de compra en estado fiscal PRELIMINARY.

    Args:
        tenant_profile (FiscalProfile): Perfil fiscal asociado.
        local_supplier (LocalSupplier): Proveedor legal de la operación.

    Returns:
        PurchaseLedgerInvoice: Comprobante del libro de compras debidamente cuadrado.
    """
    invoice = PurchaseLedgerInvoice.objects.create(
        fiscal_profile=tenant_profile,
        supplier=local_supplier,
        number="FACT-2026-001",
        invoice_control="CTRL-00099",
        document_type=PurchaseLedgerInvoice.DocumentType.INVOICE,
        purchase_type=PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        date=date(2026, 7, 15),
        application_month_year="07-2026",
        taxable_base=Decimal("1000.00"),
        exempt_amount=Decimal("0.00"),
        subtotal=Decimal("1000.00"),
        vat_percentage=PurchaseLedgerInvoice.VatPercentageChoices.GENERAL,
        vat_amount=Decimal("160.00"),
        igtf_amount=Decimal("0.00"),
        total_purchase=Decimal("1160.00"),
        status=PurchaseLedgerInvoice.InvoiceStatus.PRELIMINARY
    )
    return invoice


@pytest.fixture(scope="function")
def processed_purchase_invoice(
    tenant_profile: FiscalProfile, 
    local_supplier: LocalSupplier
) -> PurchaseLedgerInvoice:
    """Instancia una factura de compra fijada directamente en estado fiscal PROCESSED.

    Args:
        tenant_profile (FiscalProfile): Perfil fiscal asociado.
        local_supplier (LocalSupplier): Proveedor legal de la operación.

    Returns:
        PurchaseLedgerInvoice: Factura cerrada no modificable.
    """
    # Se crea directamente eludiendo el candado de mutación mediante inserción limpia
    invoice = PurchaseLedgerInvoice.objects.create(
        fiscal_profile=tenant_profile,
        supplier=local_supplier,
        number="FACT-2026-CLOSED",
        invoice_control="CTRL-00100",
        document_type=PurchaseLedgerInvoice.DocumentType.INVOICE,
        purchase_type=PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        date=date(2026, 7, 10),
        application_month_year="07-2026",
        taxable_base=Decimal("2000.00"),
        exempt_amount=Decimal("0.00"),
        subtotal=Decimal("2000.00"),
        vat_percentage=PurchaseLedgerInvoice.VatPercentageChoices.GENERAL,
        vat_amount=Decimal("320.00"),
        igtf_amount=Decimal("0.00"),
        total_purchase=Decimal("2320.00"),
        status=PurchaseLedgerInvoice.InvoiceStatus.PROCESSED
    )
    return invoice