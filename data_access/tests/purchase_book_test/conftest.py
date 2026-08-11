"""Configuración de fixtures globales para la suite de pruebas automatizadas.

Provee instancias base reutilizables de modelos y diccionarios de datos necesarios
para las pruebas del módulo de compras, aislando la preparación de datos[cite: 3].
"""

from datetime import date
from decimal import Decimal
from typing import Any
import pytest

from django.contrib.auth import get_user_model


from data_access.models.supplier import LocalSupplier
from data_access.models.base import FiscalProfile
from data_access.models.purchase_book import PurchaseLedgerInvoice
from business_logic.services.fiscal_profile_service import FiscalProfileService

User = get_user_model()

@pytest.fixture
def admin_user(db):
    """Fixture que crea y retorna un usuario operador/administrador."""
    return User.objects.create_user(
        username="admin_operator",
        email="admin@empresa.com",
        password="securepassword123",
        is_staff=True,
    )

@pytest.fixture
def base_fiscal_profile(db, admin_user):
    """Fixture que genera un perfil fiscal para contribuyente Ordinario.
    """
    service = FiscalProfileService(admin_user=admin_user)
    return service.create_fiscal_profile(
        entity_name="Comercializadora Alfa C.A.",
        use_accrual_method=True,
        fy_start_month=1,
        rif="J123456789",
        taxpayer_type=FiscalProfile.TaxpayerType.ORDINARY,
        start_period=date(2026, 1, 1)
    )

@pytest.fixture
def alternate_fiscal_profile(db, admin_user):
    """Fixture que genera un perfil fiscal para contribuyente Especial.
    """
    service = FiscalProfileService(admin_user=admin_user)
    return service.create_fiscal_profile(
        entity_name="Corporación Beta S.A.",
        use_accrual_method=False,
        fy_start_month=1,
        rif="J987654321",
        taxpayer_type=FiscalProfile.TaxpayerType.SPECIAL,
        start_period=date(2026, 1, 15)
    )

@pytest.fixture
def base_supplier(db, base_fiscal_profile):
    """Fixture para un proveedor jurídico (Con RIF)

    asociado al perfil fiscal de contribuyente ordinario.
    """
    supplier = LocalSupplier(
        fiscal_profile=base_fiscal_profile,
        name="Suministros e Insumos Alfa C.A.",
        rif="J111111111",
        supplier_type=LocalSupplier.SupplierType.WITH_RIF,
        vat_withholding_percentage=LocalSupplier.VatWithholdingPercentageChoices.SEVENTY_FIVE,
        ari_percentage=None,
    )
    supplier.full_clean()
    supplier.save()
    return supplier


@pytest.fixture
def alternate_supplier(db, alternate_fiscal_profile):
    """Fixture para un proveedor tipo Persona Natural

    asociado al perfil fiscal de contribuyente especial.
    """
    supplier = LocalSupplier(
        fiscal_profile=alternate_fiscal_profile,
        name="Juan Carlos Pérez",
        rif="V123456780",
        supplier_type=LocalSupplier.SupplierType.NATURAL,
        vat_withholding_percentage=LocalSupplier.VatWithholdingPercentageChoices.ONE_HUNDRED,
        ari_percentage=Decimal("3.00"),
    )
    supplier.full_clean()
    supplier.save()
    return supplier

@pytest.fixture
def base_invoice_data(base_supplier: LocalSupplier, base_fiscal_profile: FiscalProfile) -> dict[str, Any]:
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