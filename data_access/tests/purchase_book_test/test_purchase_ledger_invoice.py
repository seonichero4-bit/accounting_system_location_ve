"""Suite de pruebas unitarias para el modelo PurchaseLedgerInvoice.

Valida la integridad de las reglas de negocio fiscales, cálculos aritméticos,
y manejo de ciclo de vida del libro de compras[cite: 3].
"""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from dateutil.relativedelta import relativedelta

from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.base import FiscalProfile


@pytest.mark.django_db
class TestPurchaseLedgerInvoiceHappyPaths:
    """Agrupación de pruebas para los flujos exitosos (Happy Paths)[cite: 3]."""

    def test_hp_001_create_national_invoice_general_rate_success(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_HP_001] Registro exitoso de factura nacional estándar con alícuota general (16%)[cite: 3]."""
        # Arrange
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act
        invoice.clean()
        invoice.save()

        # Assert
        assert invoice.pk is not None
        assert invoice.number == "FACT-001"
        assert invoice.total_purchase == Decimal("332.00")

    def test_hp_002_number_field_sanitization_and_normalization(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_HP_002] Sanitización y normalización automática del número de documento[cite: 3]."""
        # Arrange
        base_invoice_data["number"] = " f-2026-abc "
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act
        invoice.clean()

        # Assert
        assert invoice.number == "F-2026-ABC"

    def test_hp_003_create_credit_note_linked_to_valid_invoice(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_HP_003] Registro de nota de crédito/débito vinculada a factura válida[cite: 3]."""
        # Arrange
        original_invoice = PurchaseLedgerInvoice(**base_invoice_data)
        original_invoice.save()

        credit_note_data = base_invoice_data.copy()
        credit_note_data.update({
            "document_type": PurchaseLedgerInvoice.DocumentType.CREDIT_NOTE,
            "number": "NC-001",
            "affected_invoice": original_invoice,
        })
        credit_note = PurchaseLedgerInvoice(**credit_note_data)

        # Act
        credit_note.clean()
        credit_note.save()

        # Assert
        assert credit_note.pk is not None
        assert credit_note.affected_invoice == original_invoice

    def test_hp_004_import_purchase_auto_assigns_na_to_invoice_control(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_HP_004] Registro de compra de importación con asignación automática de control[cite: 3]."""
        # Arrange
        base_invoice_data.update({
            "purchase_type": PurchaseLedgerInvoice.PurchaseType.IMPORT,
            "import_form_number": "FORM-9988",
            "import_file_number": "EXP-1234",
            "invoice_control": ""
        })
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act
        invoice.clean()

        # Assert
        assert invoice.invoice_control == "N/A"

    def test_hp_005_internal_purchase_clears_import_fields(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_HP_005] Blanqueo de datos de importación al cambiar a compra interna[cite: 3]."""
        # Arrange
        base_invoice_data.update({
            "purchase_type": PurchaseLedgerInvoice.PurchaseType.INTERNAL,
            "import_form_number": "FORM-9988",
            "import_file_number": "EXP-1234",
        })
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act
        invoice.clean()

        # Assert
        assert invoice.import_form_number is None
        assert invoice.import_file_number is None

    def test_hp_006_igtf_3_percent_calculation_success(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_HP_006] Aplicación y cálculo válido del IGTF (3%)[cite: 3]."""
        # Arrange
        base_invoice_data.update({
            "taxable_base": Decimal("100.00"),
            "vat_amount": Decimal("16.00"),
            "igtf_base": Decimal("100.00"),
            "igtf_amount": Decimal("3.00"),
            "total_purchase": Decimal("219.00") # 100(Exento) + 100(Base) + 16(IVA) + 3(IGTF)
        })
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act
        invoice.clean()

        # Assert
        assert invoice.igtf_amount == Decimal("3.00")

    def test_hp_007_anulled_status_resets_financial_amounts(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_HP_007] Anulación de documento y reinicio financiero automático[cite: 3]."""
        # Arrange
        invoice = PurchaseLedgerInvoice(**base_invoice_data)
        invoice.status = PurchaseLedgerInvoice.InvoiceStatus.ANULLED

        # Act
        invoice.clean()

        # Assert
        assert invoice.exempt_amount == Decimal("0.00")
        assert invoice.taxable_base == Decimal("0.00")
        assert invoice.total_purchase == Decimal("0.00")

    def test_hp_008_edit_and_save_preliminary_invoice(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_HP_008] Edición y actualización de documento en estado preliminar[cite: 3]."""
        # Arrange
        invoice = PurchaseLedgerInvoice(**base_invoice_data)
        invoice.save()
        
        # Act
        invoice.invoicecategory = PurchaseLedgerInvoice.InvoiceCategory.BIENE
        invoice.save()
        invoice.refresh_from_db()

        # Assert
        assert invoice.invoicecategory == PurchaseLedgerInvoice.InvoiceCategory.BIENE

    def test_hp_009_delete_preliminary_invoice_success(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_HP_009] Eliminación exitosa de documento preliminar[cite: 3]."""
        # Arrange
        invoice = PurchaseLedgerInvoice(**base_invoice_data)
        invoice.save()
        pk = invoice.pk

        # Act
        invoice.delete()

        # Assert
        assert not PurchaseLedgerInvoice.objects.filter(pk=pk).exists()

    def test_hp_010_vat_percentage_choices_as_decimal_mapping(self) -> None:
        """[ID_HP_010] Mapeo de alícuotas de IVA por enum de porcentaje[cite: 3]."""
        # Arrange & Act
        reducida = PurchaseLedgerInvoice.VatPercentageChoices.REDUCIDA.as_decimal
        adicional = PurchaseLedgerInvoice.VatPercentageChoices.ADICIONAL.as_decimal

        # Assert
        assert reducida == Decimal("8.00")
        assert adicional == Decimal("31.00")


@pytest.mark.django_db
class TestPurchaseLedgerInvoiceEdgeCases:
    """Agrupación de pruebas para los casos borde y manejo de errores (Edge Cases)[cite: 3]."""

    def test_ec_001_invalid_characters_in_document_or_control_number_raises_validation_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_001] Número de documento o control con caracteres inválidos[cite: 3]."""
        # Arrange
        base_invoice_data["number"] = "FACT#123@"
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.full_clean()
        assert "number" in exc.value.message_dict

    def test_ec_002_credit_note_without_affected_invoice_raises_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_002] Nota de crédito o débito sin factura afectada[cite: 3]."""
        # Arrange
        base_invoice_data.update({
            "document_type": PurchaseLedgerInvoice.DocumentType.CREDIT_NOTE,
            "affected_invoice": None
        })
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.clean()
        assert "affected_invoice" in exc.value.message_dict

    def test_ec_003_adjustment_note_with_different_supplier_raises_error(
        self, base_invoice_data: dict[str, Any], alternate_supplier: Any
    ) -> None:
        """[ID_EC_003] Discrepancia de proveedor entre nota de ajuste y factura afectada[cite: 3]."""
        # Arrange
        original_invoice = PurchaseLedgerInvoice(**base_invoice_data)
        original_invoice.save()

        base_invoice_data.update({
            "document_type": PurchaseLedgerInvoice.DocumentType.CREDIT_NOTE,
            "supplier": alternate_supplier,
            "affected_invoice": original_invoice
        })
        note = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            note.clean()
        assert "supplier" in exc.value.message_dict

    def test_ec_004_adjustment_note_with_different_fiscal_profile_raises_error(self, base_invoice_data: dict[str, Any], alternate_fiscal_profile: FiscalProfile) -> None:
        """[ID_EC_004] Discrepancia de perfil fiscal multi-tenant en notas de ajuste[cite: 3]."""
        # Arrange
        original_invoice = PurchaseLedgerInvoice(**base_invoice_data)
        original_invoice.save()

        base_invoice_data.update({
            "document_type": PurchaseLedgerInvoice.DocumentType.CREDIT_NOTE,
            "affected_invoice": original_invoice,
            "fiscal_profile": alternate_fiscal_profile
        })
        note = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            note.clean()
        assert "affected_invoice" in exc.value.message_dict

    def test_ec_005_adjustment_note_with_chronological_inconsistency_raises_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_005] Inconsistencia cronológica en notas de ajuste[cite: 3]."""
        # Arrange
        base_invoice_data["date"] = date.today()
        original_invoice = PurchaseLedgerInvoice(**base_invoice_data)
        original_invoice.save()

        base_invoice_data.update({
            "document_type": PurchaseLedgerInvoice.DocumentType.CREDIT_NOTE,
            "affected_invoice": original_invoice,
            "date": date.today() - relativedelta(days=5)
        })
        note = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            note.clean()
        assert "date" in exc.value.message_dict

    def test_ec_006_import_purchase_without_form_or_file_number_raises_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_006] Ausencia de planilla o expediente en compra de importación[cite: 3]."""
        # Arrange
        base_invoice_data.update({
            "purchase_type": PurchaseLedgerInvoice.PurchaseType.IMPORT,
            "import_form_number": None
        })
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.clean()
        assert "import_form_number" in exc.value.message_dict

    def test_ec_007_postdated_issue_date_raises_validation_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_007] Fecha de emisión posdatada (futura)[cite: 3]."""
        # Arrange
        base_invoice_data["date"] = date.today() + relativedelta(days=1)
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.clean()
        assert "date" in exc.value.message_dict

    def test_ec_008_fiscal_credit_expiration_over_12_months_raises_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_008] Expiración de derecho a crédito fiscal (>12 meses)[cite: 3]."""
        # Arrange
        base_invoice_data.update({
            "date": date.today() - relativedelta(months=13),
            "fiscal_period": date.today()
        })
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.clean()
        assert "date" in exc.value.message_dict

    def test_ec_009_igtf_fields_partial_interdependency_raises_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_009] Inconsistencia por interdependencia parcial en campos IGTF[cite: 3]."""
        # Arrange
        base_invoice_data.update({
            "igtf_amount": Decimal("5.00"),
            "igtf_base": Decimal("0.00")
        })
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.clean()
        assert "igtf_amount" in exc.value.message_dict

    def test_ec_010_igtf_amount_deviating_from_3_percent_raises_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_010] Cálculo numérico de IGTF discordante del 3%[cite: 3]."""
        # Arrange
        base_invoice_data.update({
            "igtf_base": Decimal("100.00"),
            "igtf_amount": Decimal("5.00") # Debería ser 3.00
        })
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.clean()
        assert "igtf_amount" in exc.value.message_dict

    def test_ec_011_igtf_base_exceeding_gross_subtotal_raises_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_011] Base IGTF superior al subtotal bruto[cite: 3]."""
        # Arrange
        base_invoice_data.update({
            "exempt_amount": Decimal("20.00"),
            "taxable_base": Decimal("30.00"),
            "igtf_base": Decimal("100.00"), # 100 > (20+30)
            "igtf_amount": Decimal("3.00")
        })
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.clean()
        assert "igtf_base" in exc.value.message_dict

    def test_ec_012_vat_amount_arithmetic_mismatch_raises_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_012] Descuadre numérico del monto de IVA por alícuota[cite: 3]."""
        # Arrange
        base_invoice_data.update({
            "taxable_base": Decimal("100.00"),
            "vat_percentage": PurchaseLedgerInvoice.VatPercentageChoices.GENERAL,
            "vat_amount": Decimal("25.00") # Debería ser 16.00
        })
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.clean()
        assert "vat_amount" in exc.value.message_dict

    def test_ec_013_total_purchase_arithmetic_mismatch_raises_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_013] Descuadre en la suma aritmética del total general[cite: 3]."""
        # Arrange
        base_invoice_data.update({
            "exempt_amount": Decimal("10.00"),
            "taxable_base": Decimal("100.00"),
            "vat_amount": Decimal("16.00"),
            "total_purchase": Decimal("500.00") # Debería ser 126.00
        })
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.clean()
        assert "total_purchase" in exc.value.message_dict

    def test_ec_014_modify_processed_document_raises_validation_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_014] Bloqueo de modificación sobre documento procesado (PROCESSED)[cite: 3]."""
        # Arrange
        invoice = PurchaseLedgerInvoice(**base_invoice_data)
        invoice.status = PurchaseLedgerInvoice.InvoiceStatus.PROCESSED
        invoice.save()

        # Act & Assert
        invoice.number = "FACT-002"
        with pytest.raises(ValidationError) as exc:
            invoice.save()
        assert "Bloqueo de Modificación Fiscal" in str(exc.value)

    def test_ec_015_delete_processed_document_raises_validation_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_015] Bloqueo de eliminación sobre documento procesado (PROCESSED)[cite: 3]."""
        # Arrange
        invoice = PurchaseLedgerInvoice(**base_invoice_data)
        invoice.status = PurchaseLedgerInvoice.InvoiceStatus.PROCESSED
        invoice.save()

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.delete()
        assert "Bloqueo de Eliminación Fiscal" in str(exc.value)

    def test_ec_016_delete_anulled_processed_document_raises_validation_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_016] Bloqueo de eliminación sobre documento anulado procesado (ANULLED_PROCESSED)[cite: 3]."""
        # Arrange
        invoice = PurchaseLedgerInvoice(**base_invoice_data)
        invoice.status = PurchaseLedgerInvoice.InvoiceStatus.ANULLED_PROCESSED
        invoice.save()

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.delete()
        assert "Bloqueo de Eliminación Fiscal" in str(exc.value)

    def test_ec_017_invalid_vat_percentage_choice_raises_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_017] Ingreso de alícuota de IVA fuera de catálogo enumerado[cite: 3]."""
        # Arrange
        base_invoice_data.update({
            "vat_percentage": 99,
            "taxable_base": Decimal("100.00"),
            "vat_amount": Decimal("16.00"), # Al fallar enum, calcula con 0.00 y detecta descuadre
        })
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.clean()
        assert "vat_amount" in exc.value.message_dict

    def test_ec_018_negative_financial_amounts_raises_validation_error(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_018] Ingreso de montos financieros negativos[cite: 3]."""
        # Arrange
        base_invoice_data["exempt_amount"] = Decimal("-10.00")
        invoice = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            invoice.full_clean()
        assert "exempt_amount" in exc.value.message_dict

    def test_ec_019_unique_constraint_violation_for_fiscal_document(self, base_invoice_data: dict[str, Any]) -> None:
        """[ID_EC_019] Violación de restricción de unicidad de documento fiscal[cite: 3]."""
        # Arrange
        invoice_one = PurchaseLedgerInvoice(**base_invoice_data)
        invoice_one.save()

        invoice_two = PurchaseLedgerInvoice(**base_invoice_data)

        # Act & Assert
        with pytest.raises(IntegrityError):
            invoice_two.save()