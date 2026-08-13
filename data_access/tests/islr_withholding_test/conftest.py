"""Configuración de fixtures globales para la suite de pruebas automatizadas.

Provee instancias base reutilizables de modelos y diccionarios de datos necesarios
para las pruebas del módulo de compras, aislando la preparación de datos.
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
    """Fixture que genera un perfil fiscal para contribuyente Ordinario."""
    service = FiscalProfileService(admin_user=admin_user)
    profile = service.create_fiscal_profile(
        entity_name="Comercializadora Alfa C.A.",
        use_accrual_method=True,
        fy_start_month=1,
        rif="J123456789",
        taxpayer_type=FiscalProfile.TaxpayerType.ORDINARY,
        start_period=date(2026, 1, 1)
    )
    # Atributo necesario para el cálculo de UT en el modelo
    profile.ut = Decimal("9.00")
    profile.save()
    return profile

@pytest.fixture
def base_supplier(db, base_fiscal_profile):
    """Fixture para un proveedor jurídico (Con RIF)."""
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
def base_invoice_data(base_supplier, base_fiscal_profile) -> dict[str, Any]:
    """Provee un diccionario con datos válidos para una factura estándar."""
    return {
        "transaction_type": PurchaseLedgerInvoice.TransactionType.REGISTRO,
        "document_type": PurchaseLedgerInvoice.DocumentType.INVOICE,
        "purchase_type": PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        "number": "fact-001",
        "invoice_control": "CTRL-001",
        "supplier": base_supplier,
        "date": date(2026, 8, 1),
        "fiscal_period": date(2026, 8, 1),
        "exempt_amount": Decimal("0.00"),
        "taxable_base": Decimal("1000.00"),
        "vat_percentage": PurchaseLedgerInvoice.VatPercentageChoices.GENERAL,
        "vat_amount": Decimal("160.00"),
        "total_purchase": Decimal("1160.00"),
        "status": "PRELIMINARY",
        "fiscal_profile": base_fiscal_profile,
    }

@pytest.fixture
def preliminary_invoice(db, base_invoice_data):
    """Fixture de factura en estado PRELIMINARY para pruebas unitarias."""
    invoice = PurchaseLedgerInvoice.objects.create(**base_invoice_data)
    # Se emula la propiedad subtotal para los cálculos
    invoice.subtotal = Decimal("1000.00") 
    invoice.save()
    return invoice

@pytest.fixture
def processed_invoice(db, base_invoice_data):
    """Fixture de factura en estado PROCESSED para pruebas de reglas de negocio."""
    data = base_invoice_data.copy()
    data["status"] = "PROCESSED"
    data["number"] = "fact-002"
    data["invoice_control"] = "CTRL-002"
    data["date"] = date(2026, 8, 20)
    invoice = PurchaseLedgerInvoice.objects.create(**data)
    invoice.subtotal = Decimal("1000.00")
    invoice.save()
    return invoice