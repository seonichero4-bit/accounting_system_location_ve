"""Suite de pruebas de integración para el servicio PurchaseLedgerExcelBuilder."""

from datetime import date
from decimal import Decimal
from typing import List

from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.vat_withholding import VatWithholdingCertificate
from data_access.models.base import FiscalProfile
# Se asume la importación correcta del constructor según la estructura del proyecto
from business_logic.services.purchaseledgerexcelbuilderservice import PurchaseLedgerExcelBuilder


def test_id_hp_001_update_summary_internal_purchase_general_deductible(
    fiscal_profile: FiscalProfile,
    invoice: PurchaseLedgerInvoice,
    excel_queryset: List[PurchaseLedgerInvoice]
) -> None:
    """
    [ID_HP_001] - Validar que una factura de compra interna estándar incremente 
    correctamente los acumuladores de deducibilidad, compras no gravadas y general.
    """
    # Arrange
    invoice.document_type = PurchaseLedgerInvoice.DocumentType.INVOICE
    invoice.deductibility = PurchaseLedgerInvoice.Deductibility.DEDUCIBLE
    invoice.purchase_type = PurchaseLedgerInvoice.PurchaseType.INTERNAL
    invoice.vat_percentage = PurchaseLedgerInvoice.VatPercentageChoices.GENERAL.value
    invoice.taxable_base = Decimal("100.00")
    invoice.vat_amount = Decimal("16.00")
    invoice.exempt_amount = Decimal("10.00")
    invoice.amount_exonerated = Decimal("0.00")
    invoice.amount_not_subject = Decimal("0.00")
    invoice.amount_without_right_to_credit = Decimal("0.00")

    builder = PurchaseLedgerExcelBuilder(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 1, 1),
        queryset=excel_queryset
    )
    builder.is_special_taxpayer = False

    # Act
    builder._update_summary_totals(invoice, is_adjustment=False)

    # Assert
    assert builder.summary['Credito fiscal totalmente deducible'] == Decimal("16.00")
    assert builder.summary['no_gravadas'] == Decimal("10.00")
    assert builder.summary['internal_gen_base'] == Decimal("100.00")
    assert builder.summary['internal_gen_vat'] == Decimal("16.00")


def test_id_hp_002_update_summary_import_credit_note_reduced_partial(
    fiscal_profile: FiscalProfile,
    invoice: PurchaseLedgerInvoice,
    excel_queryset: List[PurchaseLedgerInvoice]
) -> None:
    """
    [ID_HP_002] - Verificar que una nota de crédito de importación aplique 
    el factor multiplicador negativo (-1) sobre los acumuladores.
    """
    # Arrange
    invoice.document_type = PurchaseLedgerInvoice.DocumentType.CREDIT_NOTE
    invoice.deductibility = PurchaseLedgerInvoice.Deductibility.PARCIALMENTE_DEDUCIBLE
    invoice.purchase_type = PurchaseLedgerInvoice.PurchaseType.IMPORT
    invoice.vat_percentage = PurchaseLedgerInvoice.VatPercentageChoices.REDUCIDA.value
    invoice.taxable_base = Decimal("200.00")
    invoice.vat_amount = Decimal("16.00")
    invoice.exempt_amount = Decimal("50.00")
    invoice.amount_exonerated = Decimal("0.00")
    invoice.amount_not_subject = Decimal("0.00")
    invoice.amount_without_right_to_credit = Decimal("0.00")

    builder = PurchaseLedgerExcelBuilder(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 1, 1),
        queryset=excel_queryset
    )
    builder.is_special_taxpayer = False

    # Act
    builder._update_summary_totals(invoice, is_adjustment=False)

    # Assert
    assert builder.summary['Credito fiscal parcialmente deducible'] == Decimal("-16.00")
    assert builder.summary['no_gravadas'] == Decimal("-50.00")
    assert builder.summary['import_red_base'] == Decimal("-200.00")
    assert builder.summary['import_red_vat'] == Decimal("-16.00")


def test_id_hp_003_update_summary_internal_purchase_additional_rate(
    fiscal_profile: FiscalProfile,
    invoice: PurchaseLedgerInvoice,
    excel_queryset: List[PurchaseLedgerInvoice]
) -> None:
    """
    [ID_HP_003] - Validar el direccionamiento hacia los acumuladores de alícuota 
    adicional para operaciones de compra nacional.
    """
    # Arrange
    invoice.document_type = PurchaseLedgerInvoice.DocumentType.INVOICE
    invoice.purchase_type = PurchaseLedgerInvoice.PurchaseType.INTERNAL
    invoice.vat_percentage = PurchaseLedgerInvoice.VatPercentageChoices.ADICIONAL.value
    invoice.taxable_base = Decimal("300.00")
    invoice.vat_amount = Decimal("45.00")
    
    # Valores por defecto para evitar arrastre de sumas impredecibles
    invoice.exempt_amount = Decimal("0.00")
    invoice.amount_exonerated = Decimal("0.00")
    invoice.amount_not_subject = Decimal("0.00")
    invoice.amount_without_right_to_credit = Decimal("0.00")

    builder = PurchaseLedgerExcelBuilder(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 1, 1),
        queryset=excel_queryset
    )
    builder.is_special_taxpayer = False

    # Act
    builder._update_summary_totals(invoice, is_adjustment=False)

    # Assert
    assert builder.summary['internal_adi_base'] == Decimal("300.00")
    assert builder.summary['internal_adi_vat'] == Decimal("45.00")


def test_id_hp_004_update_summary_previous_period_adjustment(
    fiscal_profile: FiscalProfile,
    invoice: PurchaseLedgerInvoice,
    excel_queryset: List[PurchaseLedgerInvoice]
) -> None:
    """
    [ID_HP_004] - Confirmar que al marcar is_adjustment=True, se acumule en 
    las métricas de ajustes y no en operaciones corrientes.
    """
    # Arrange
    invoice.document_type = PurchaseLedgerInvoice.DocumentType.INVOICE
    invoice.deductibility = PurchaseLedgerInvoice.Deductibility.DEDUCIBLE
    invoice.taxable_base = Decimal("500.00")
    invoice.vat_amount = Decimal("80.00")
    invoice.exempt_amount = Decimal("100.00")
    invoice.vat_percentage = PurchaseLedgerInvoice.VatPercentageChoices.GENERAL.value
    
    invoice.amount_exonerated = Decimal("0.00")
    invoice.amount_not_subject = Decimal("0.00")
    invoice.amount_without_right_to_credit = Decimal("0.00")

    builder = PurchaseLedgerExcelBuilder(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 1, 1),
        queryset=excel_queryset
    )

    # Act
    builder._update_summary_totals(invoice, is_adjustment=True)

    # Assert
    assert builder.summary['Credito fiscal totalmente deducible'] == Decimal("80.00")
    assert builder.summary['ajustes_base'] == Decimal("500.00")
    assert builder.summary['ajustes_vat'] == Decimal("80.00")
    assert builder.summary['no_gravadas'] == Decimal("0.00")  # Permanece intacto
    assert builder.summary['internal_gen_base'] == Decimal("0.00")  # Permanece intacto


def test_id_hp_005_update_summary_special_taxpayer_withholding(
    fiscal_profile: FiscalProfile,
    invoice: PurchaseLedgerInvoice,
    vat_certificate: VatWithholdingCertificate,
    excel_queryset: List[PurchaseLedgerInvoice]
) -> None:
    """
    [ID_HP_005] - Validar que un contribuyente especial acumule el monto 
    retenido cuando existe un comprobante asociado en una operación corriente.
    """
    # Arrange
    invoice.document_type = PurchaseLedgerInvoice.DocumentType.INVOICE
    invoice.vat_percentage = PurchaseLedgerInvoice.VatPercentageChoices.GENERAL.value
    invoice.taxable_base = Decimal("100.00")
    invoice.vat_amount = Decimal("16.00")
    
    # Carga de valores por defecto
    invoice.exempt_amount = Decimal("0.00")
    invoice.amount_exonerated = Decimal("0.00")
    invoice.amount_not_subject = Decimal("0.00")
    invoice.amount_without_right_to_credit = Decimal("0.00")

    # Vinculación explícita en memoria para soportar getattr en el código objetivo
    vat_certificate.vat_withheld_amount = Decimal("12.00")
    invoice.vat_withholding_certificate = vat_certificate

    builder = PurchaseLedgerExcelBuilder(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 1, 1),
        queryset=excel_queryset
    )
    # Sobreescribimos la variable de instancia según requerimiento del plan
    builder.is_special_taxpayer = True

    # Act
    builder._update_summary_totals(invoice, is_adjustment=False)

    # Assert
    assert builder.summary['retenciones_periodo'] == Decimal("12.00")
    assert builder.summary['internal_gen_base'] == Decimal("100.00")
    assert builder.summary['internal_gen_vat'] == Decimal("16.00")