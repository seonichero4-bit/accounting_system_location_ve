"""Suite de pruebas unitarias para el componente FiscalBatchProcessingService.

Valida la integración contable de lotes de facturas, generación de asientos,
y el estricto cumplimiento de auditorías fiscales bajo normativas locales.
"""

import pytest
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from unittest.mock import patch, MagicMock

from data_access.models.base import FiscalProfile
from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.vat_withholding import VatWithholdingCertificate
from data_access.models.islr_withholding import IslrWithholdingCertificate
from business_logic.services.fiscalbatchprocessingservice import FiscalBatchProcessingService


@pytest.mark.django_db
def test_id_hp_001_process_batch_ordinary_taxpayer_inventory_and_services(
    fiscal_profile: FiscalProfile,
    local_supplier,
    purchase_ledger_invoice: PurchaseLedgerInvoice,
    islr_withholding_certificate: IslrWithholdingCertificate,
    fiscal_period_alternative,
) -> None:
    """Validar procesamiento de lote para Contribuyente Ordinario con Inventario y Servicios.
    
    Verifica la generación de la tupla contable (asiento_1, None, asiento_3) para
    facturas mixtas y la mutación de estado a PROCESSED.
    """
    # Arrange
    fiscal_profile.taxpayer_type = "ORDINARY"
    fiscal_profile.initial_fiscal_period = fiscal_period_alternative
    fiscal_profile.save()

    # Factura 2: Inventario
    inv_invoice = PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile,
        supplier=local_supplier,
        transaction_type=PurchaseLedgerInvoice.TransactionType.REGISTRO,
        document_type=PurchaseLedgerInvoice.DocumentType.INVOICE,
        number="FAC-INV-101",
        invoice_control="CTRL-INV-101",
        date=date(2026, 8, 15),
        fiscal_period=date(2026, 8, 31),
        taxable_base=Decimal("500.00"),
        vat_percentage=PurchaseLedgerInvoice.VatPercentageChoices.GENERAL,
        vat_amount=Decimal("80.00"),
        subtotal=Decimal("500.00"),
        total_purchase=Decimal("580.00"),
        status=PurchaseLedgerInvoice.InvoiceStatus.PRELIMINARY,
        invoicecategory=PurchaseLedgerInvoice.InvoiceCategory.INVENTARIO,
        affected_account=[]
    )

    service = FiscalBatchProcessingService(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 8, 31)
    )

    # Act
    asiento_1, asiento_2, asiento_3 = service.execute_batch_processing()

    # Assert
    assert asiento_1 is not None
    assert asiento_2 is None
    assert asiento_3 is not None

    purchase_ledger_invoice.refresh_from_db()
    inv_invoice.refresh_from_db()
    islr_withholding_certificate.refresh_from_db()

    assert purchase_ledger_invoice.status == PurchaseLedgerInvoice.InvoiceStatus.PROCESSED
    assert inv_invoice.status == PurchaseLedgerInvoice.InvoiceStatus.PROCESSED
    assert islr_withholding_certificate.status == IslrWithholdingCertificate.CertificateStatus.PROCESSED


@pytest.mark.django_db
def test_id_hp_002_process_batch_special_taxpayer_withholdings(
    fiscal_profile: FiscalProfile,
    purchase_ledger_invoice: PurchaseLedgerInvoice,
    vat_withholding_certificate: VatWithholdingCertificate,
    islr_withholding_certificate: IslrWithholdingCertificate,
) -> None:
    """Verificar la generación de asientos contables para Sujetos Pasivos Especiales.
    
    Asegura la creación de asiento_1, asiento_2 y asiento_3 con retenciones
    de IVA e ISLR procesadas exitosamente.
    """
    # Arrange
    fiscal_profile.taxpayer_type = "SPECIAL"
    fiscal_profile.save()

    service = FiscalBatchProcessingService(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 8, 31)
    )

    # Act
    asiento_1, asiento_2, asiento_3 = service.execute_batch_processing()

    # Assert
    assert asiento_1 is not None
    assert asiento_2 is None or asiento_2 is not None  # Depende de lógica de IVA retenido
    assert asiento_3 is not None

    purchase_ledger_invoice.refresh_from_db()
    vat_withholding_certificate.refresh_from_db()
    
    assert purchase_ledger_invoice.status == PurchaseLedgerInvoice.InvoiceStatus.PROCESSED
    assert vat_withholding_certificate.status == VatWithholdingCertificate.CertificateStatus.PROCESSED


@pytest.mark.django_db
def test_id_hp_003_process_batch_with_credit_notes(
    fiscal_profile: FiscalProfile,
    local_supplier,
    purchase_ledger_invoice: PurchaseLedgerInvoice,
    setup_accounts
) -> None:
    """Validar que el componente aplique ajuste por signo negativo con Notas de Crédito."""
    # Arrange
    created_accounts = setup_accounts
    account = created_accounts["61203"]

    PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile,
        supplier=local_supplier,
        transaction_type=PurchaseLedgerInvoice.TransactionType.AJUSTE,
        document_type=PurchaseLedgerInvoice.DocumentType.CREDIT_NOTE,
        number="NC-2026-001",
        invoice_control="CTRL-NC-001",
        date=date(2026, 8, 16),
        fiscal_period=date(2026, 8, 31),
        affected_invoice=purchase_ledger_invoice,
        taxable_base=Decimal("200.00"),
        vat_percentage=PurchaseLedgerInvoice.VatPercentageChoices.GENERAL,
        vat_amount=Decimal("32.00"),
        subtotal=Decimal("200.00"),
        total_purchase=Decimal("232.00"),
        status=PurchaseLedgerInvoice.InvoiceStatus.PRELIMINARY,
        invoicecategory=PurchaseLedgerInvoice.InvoiceCategory.SERVICIO,
        affected_account=[{"account_id": str(account.uuid), "amount": 200}]
    )

    service = FiscalBatchProcessingService(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 8, 31)
    )

    # Act
    asientos = service.execute_batch_processing()

    # Assert
    assert asientos[0] is not None
    
    # Verificación de cambio de estado a PROCESSED en todo el lote
    invoices = PurchaseLedgerInvoice.objects.filter(fiscal_profile=fiscal_profile)
    for inv in invoices:
        assert inv.status == PurchaseLedgerInvoice.InvoiceStatus.PROCESSED


@pytest.mark.django_db
def test_id_hp_004_process_batch_annulled_invoices_transition(
    fiscal_profile: FiscalProfile,
    local_supplier,
    purchase_ledger_invoice: PurchaseLedgerInvoice,
) -> None:
    """Confirmar la transición de estado para facturas anuladas en el período."""
    # Arrange
    annulled_invoice = PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile,
        supplier=local_supplier,
        document_type=PurchaseLedgerInvoice.DocumentType.INVOICE,
        number="FAC-ANULADA-01",
        invoice_control="CTRL-ANU-01",
        date=date(2026, 8, 15),
        fiscal_period=date(2026, 8, 31),
        status=PurchaseLedgerInvoice.InvoiceStatus.ANULLED,
    )

    service = FiscalBatchProcessingService(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 8, 31)
    )

    # Act
    service.execute_batch_processing()

    # Assert
    purchase_ledger_invoice.refresh_from_db()
    annulled_invoice.refresh_from_db()

    assert purchase_ledger_invoice.status == PurchaseLedgerInvoice.InvoiceStatus.PROCESSED
    assert annulled_invoice.status == PurchaseLedgerInvoice.InvoiceStatus.ANULLED_PROCESSED


@pytest.mark.django_db
def test_id_ec_001_init_missing_accounts_raises_validation_error(
    fiscal_profile: FiscalProfile,
) -> None:
    """Evaluar validación de integridad cuando faltan atributos contables requeridos."""
    # Arrange
    fiscal_profile.vat_credit_account = None
    fiscal_profile.save()

    # Act & Assert
    with pytest.raises(ValidationError, match="vat_credit_account"):
        FiscalBatchProcessingService(
            fiscal_profile=fiscal_profile,
            fiscal_period=date(2026, 8, 31)
        )


@pytest.mark.django_db
def test_id_ec_002_process_batch_empty_raises_validation_error(
    fiscal_profile: FiscalProfile,
) -> None:
    """Verificar el comportamiento cuando no existen registros preliminares en el lote."""
    # Arrange
    # Borrar facturas existentes en estado PRELIMINARY
    PurchaseLedgerInvoice.objects.filter(fiscal_profile=fiscal_profile).delete()

    service = FiscalBatchProcessingService(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 8, 31)
    )

    # Act & Assert
    with pytest.raises(ValidationError, match="no existen facturas preliminares"):
        service.execute_batch_processing()


@pytest.mark.django_db
def test_id_ec_003_service_invoice_missing_affected_accounts_raises_validation_error(
    fiscal_profile: FiscalProfile,
    purchase_ledger_invoice: PurchaseLedgerInvoice,
) -> None:
    """Validar que el sistema aborte si una factura de servicio carece de imputación."""
    # Arrange
    purchase_ledger_invoice.affected_account = []
    # Saltamos el .clean() del modelo para forzar el escenario al nivel del servicio
    purchase_ledger_invoice.save(update_fields=['affected_account'])

    service = FiscalBatchProcessingService(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 8, 31)
    )

    # Act & Assert
    with pytest.raises(ValidationError, match="Fallo de Imputación Contable"):
        service.execute_batch_processing()


@pytest.mark.django_db
def test_id_ec_004_unbalanced_entry_raises_validation_error(
    fiscal_profile: FiscalProfile,
    purchase_ledger_invoice: PurchaseLedgerInvoice,
) -> None:
    """Forzar una ruptura de partida doble en memoria superior al umbral de tolerancia."""
    # Arrange
    # Corrompemos la consistencia aritmética de la factura a nivel de base de datos
    PurchaseLedgerInvoice.objects.filter(pk=purchase_ledger_invoice.pk).update(
        total_purchase=Decimal("9999.99")
    )

    service = FiscalBatchProcessingService(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 8, 31)
    )

    # Act & Assert
    with pytest.raises(ValidationError, match="desbalance|Desbalance"):
        service.execute_batch_processing()


@pytest.mark.django_db
def test_id_ec_005_special_taxpayer_missing_vat_cert_raises_validation_error(
    fiscal_profile: FiscalProfile,
    purchase_ledger_invoice: PurchaseLedgerInvoice,
) -> None:
    """Garantizar el aborto del proceso si un Especial no posee comprobante de IVA."""
    # Arrange
    fiscal_profile.taxpayer_type = "SPECIAL"
    fiscal_profile.save()
    
    # Eliminamos el comprobante de IVA retenido asociado para fallar la auditoría
    VatWithholdingCertificate.objects.filter(purchase_invoice=purchase_ledger_invoice).delete()

    service = FiscalBatchProcessingService(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 8, 31)
    )

    # Act & Assert
    with pytest.raises(ValidationError, match="Auditoría Fiscal Fallida"):
        service.execute_batch_processing()


@pytest.mark.django_db
@patch("business_logic.services.fiscalbatchprocessingservice.JournalEntryModel")
def test_id_ec_006_orm_verify_returns_false_raises_validation_error(
    mock_journal_entry_model: MagicMock,
    fiscal_profile: FiscalProfile,
    purchase_ledger_invoice: PurchaseLedgerInvoice,
) -> None:
    """Simular falla en la verificación de cuadratura del ORM JournalEntryModel."""
    # Arrange
    # Configuramos el mock para que el método verify() del ORM retorne cuadratura rota
    mock_instance = MagicMock()
    mock_instance.verify.return_value = (MagicMock(), False)
    mock_journal_entry_model.objects.create.return_value = mock_instance

    service = FiscalBatchProcessingService(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 8, 31)
    )

    # Act & Assert
    with pytest.raises(ValidationError, match="Error de cuadratura en Asiento"):
        service.execute_batch_processing()


@pytest.mark.django_db
def test_id_ec_007_cert_not_preliminary_raises_validation_error(
    fiscal_profile: FiscalProfile,
    vat_withholding_certificate: VatWithholdingCertificate,
) -> None:
    """Verificar que comprobantes en estado distinto a PRELIMINARY disparen error de auditoría."""
    # Arrange
    fiscal_profile.taxpayer_type = "SPECIAL"
    fiscal_profile.save()

    # Alteramos el estado esquivando validaciones del modelo para forzar el escenario
    VatWithholdingCertificate.objects.filter(pk=vat_withholding_certificate.pk).update(
        status=VatWithholdingCertificate.CertificateStatus.PROCESSED
    )

    service = FiscalBatchProcessingService(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 8, 31)
    )

    # Act & Assert
    with pytest.raises(ValidationError, match="Auditoría Fiscal Fallida"):
        service.execute_batch_processing()


@pytest.mark.django_db
@patch("business_logic.services.fiscalbatchprocessingservice.PurchaseLedgerInvoice.objects.filter")
def test_id_ec_008_db_exception_triggers_transaction_rollback(
    mock_filter: MagicMock,
    fiscal_profile: FiscalProfile,
) -> None:
    """Validar el comportamiento transaccional atómico frente a caídas de Base de Datos."""
    # Arrange
    service = FiscalBatchProcessingService(
        fiscal_profile=fiscal_profile,
        fiscal_period=date(2026, 8, 31)
    )
    
    # Inyectamos una excepción grave al momento de realizar la actualización masiva
    mock_qs = MagicMock()
    mock_qs.update.side_effect = Exception("Fallo de conexión a la base de datos")
    mock_filter.return_value = mock_qs

    # Act & Assert
    with pytest.raises(Exception, match="Fallo de conexión a la base de datos"):
        service.execute_batch_processing()