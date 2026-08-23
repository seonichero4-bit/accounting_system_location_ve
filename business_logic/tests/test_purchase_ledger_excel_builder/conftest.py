"""Configuración de fixtures y dependencias para la suite de pruebas."""

from datetime import date
from decimal import Decimal
from typing import List

import pytest
from django.contrib.auth.models import User

from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.vat_withholding import VatWithholdingCertificate
from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.base import FiscalProfile


@pytest.fixture
def admin_user(db) -> User:
    """
    Proporciona un usuario administrador en base de datos requerido
    para la instanciación de servicios contables.
    """
    return User.objects.create_superuser(
        username="admin_test", email="admin@test.com", password="password"
    )


@pytest.fixture
def fiscal_profile(admin_user: User) -> FiscalProfile:
    """
    Construye y persiste un perfil fiscal real utilizando el servicio de negocio,
    garantizando la integridad relacional de la entidad y el periodo.
    """
    service = FiscalProfileService(admin_user=admin_user)
    return service.create_fiscal_profile(
        entity_name="Empresa Test C.A.",
        use_accrual_method=True,
        fy_start_month=1,
        rif="J-12345678-9",
        taxpayer_type="ORDINARY",
        start_period=date(2026, 1, 1),
    )


@pytest.fixture
def invoice() -> PurchaseLedgerInvoice:
    """
    Suministra una instancia en memoria (sin persistir) del modelo
    PurchaseLedgerInvoice preparada para manipulación en las pruebas.
    """
    return PurchaseLedgerInvoice(
        document_type=PurchaseLedgerInvoice.DocumentType.INVOICE,
        deductibility=PurchaseLedgerInvoice.Deductibility.DEDUCIBLE,
        purchase_type=PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        vat_percentage=PurchaseLedgerInvoice.VatPercentageChoices.GENERAL,
        taxable_base=Decimal("0.00"),
        vat_amount=Decimal("0.00"),
        exempt_amount=Decimal("0.00"),
        amount_exonerated=Decimal("0.00"),
        amount_not_subject=Decimal("0.00"),
        amount_without_right_to_credit=Decimal("0.00"),
    )


@pytest.fixture
def vat_certificate(invoice: PurchaseLedgerInvoice) -> VatWithholdingCertificate:
    """
    Suministra una instancia en memoria de VatWithholdingCertificate,
    vinculada lógicamente a la instancia de factura en memoria.
    """
    return VatWithholdingCertificate(
        purchase_invoice=invoice,
        application_date=date(2026, 1, 15),
        vat_withholding_percentage=VatWithholdingCertificate.VatWithholdingChoices.SETENTA_Y_CINCO,
        document_number="20260100000001",
        vat_withheld_amount=Decimal("0.00"),
    )


@pytest.fixture
def excel_queryset() -> List[PurchaseLedgerInvoice]:
    """
    Proporciona un queryset simulado (lista vacía) para cumplir con el 
    contrato de instanciación del servicio PurchaseLedgerExcelBuilder.
    """
    return []