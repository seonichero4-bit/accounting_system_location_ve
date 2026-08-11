"""Configuración de fixtures globales para la suite de pruebas automatizadas.

Provee instancias base reutilizables de modelos y diccionarios de datos necesarios
para las pruebas del módulo de compras, aislando la preparación de datos[cite: 3].
"""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from data_access.models.supplier import LocalSupplier
from data_access.models.base import FiscalProfile
from data_access.models.purchase_book import PurchaseLedgerInvoice

@pytest.fixture
def base_fiscal_profile(db: Any) -> FiscalProfile:
    """Tenant una instancia persistida de un Perfil fiscal.

    Returns:
        FiscalProfile: Perfil fiscal genérico para pruebas.
    """
    fiscal_profile = FiscalProfile.objects.get(rif="J123456784")
    return fiscal_profile

@pytest.fixture
def alternate_fiscal_profile(db: Any) -> FiscalProfile:
    """Tenant secundario para pruebas de discrepancia relacional.

    Returns:
        FiscalProfile: Perfil fiscal secundario de pruebas.
    """
    fiscal_profile = FiscalProfile.objects.get(rif="J123456775")
    return fiscal_profile

@pytest.fixture
def base_supplier(db: Any) -> LocalSupplier:
    """Provee una instancia persistida de un proveedor local[cite: 3].

    Returns:
        LocalSupplier: Proveedor genérico para pruebas.
    """
    supplier = LocalSupplier.objects.filter(pk=2).first
    return supplier


@pytest.fixture
def alternate_supplier(db: Any) -> LocalSupplier:
    """Provee un proveedor secundario para pruebas de discrepancia relacional[cite: 3].

    Returns:
        LocalSupplier: Proveedor secundario de pruebas.
    """
    supplier = LocalSupplier.objects.get(rif="J123456157")
    return supplier


@pytest.fixture
def base_invoice_data(base_supplier: LocalSupplier) -> dict[str, Any]:
    """Provee un diccionario con datos válidos para una factura estándar[cite: 3].

    Alineado con los requisitos aritméticos y fiscales del modelo.

    Returns:
        dict[str, Any]: Diccionario con parámetros para instanciar PurchaseLedgerInvoice.
    """
    return {
        "transaction_type": PurchaseLedgerInvoice.TransactionType.REGISTRO,
        "document_type": PurchaseLedgerInvoice.DocumentType.INVOICE,
        "purchase_type": PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        "number": "fact-001",
        "invoice_control": "CTRL-001",
        "supplier": base_supplier,
        "date": date.today(),
        "fiscal_period": date.today(),
        "exempt_amount": Decimal("100.00"),
        "taxable_base": Decimal("200.00"),
        "vat_percentage": PurchaseLedgerInvoice.VatPercentageChoices.GENERAL,
        "vat_amount": Decimal("32.00"),
        "total_purchase": Decimal("332.00"),
        "status": PurchaseLedgerInvoice.InvoiceStatus.PRELIMINARY,
        "fiscal_profile": base_fiscal_profile, 
    }