"""Suite de pruebas unitarias para el modelo CreditNoteSettlement.

Implementa los casos de prueba definidos en el plan de pruebas
para garantizar el correcto cuadre operativo y financiero
de las liquidaciones de Notas de Crédito, sin usar mocks.
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from data_access.models.credit_note_settlement import CreditNoteSettlement
from data_access.models.sales_record import SalesRecord


@pytest.mark.django_db
class TestCreditNoteSettlementHappyPaths:
    """Suite de Pruebas Unitarias - Flujos Felices (Happy Paths)."""

    def test_ID_HP_001_returns_with_mixed_payment(self, credit_note_sales_record, credit_note_settlement_factory):
        """Valida liquidación de devolución de bienes con pago mixto (efectivo y transferencia)."""
        # Arrange
        credit_note_sales_record.sale_category = SalesRecord.SaleCategory.GOODS
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["sale_category", "total_sales_inc_vat"])

        # Act
        settlement = credit_note_settlement_factory(
            sales_record=credit_note_sales_record,
            settlement_type=CreditNoteSettlement.SettlementType.RETURNS,
            returned_goods_value=Decimal("100.00"),
            reimbursement_in_services=Decimal("0.00"),
            commercial_discount_amount=Decimal("0.00"),
            bank_transfer_amount=Decimal("50.00"),
            cash_amount=Decimal("50.00"),
            refunded_amount=Decimal("100.00"),
            payment_reference="TRX-98765",
            validate=True
        )

        # Assert
        assert settlement.pk is not None
        assert settlement.settlement_type == CreditNoteSettlement.SettlementType.RETURNS
        assert settlement.refunded_amount == Decimal("100.00")

    def test_ID_HP_002_returns_in_services_category(self, credit_note_sales_record, credit_note_settlement_factory):
        """Valida registro de devolución de tipo RETURNS en una venta categorizada como servicios."""
        # Arrange
        credit_note_sales_record.sale_category = SalesRecord.SaleCategory.SERVICES
        credit_note_sales_record.total_sales_inc_vat = Decimal("150.00")
        credit_note_sales_record.save(update_fields=["sale_category", "total_sales_inc_vat"])

        # Act
        settlement = credit_note_settlement_factory(
            sales_record=credit_note_sales_record,
            settlement_type=CreditNoteSettlement.SettlementType.RETURNS,
            returned_goods_value=Decimal("0.00"),
            reimbursement_in_services=Decimal("150.00"),
            commercial_discount_amount=Decimal("0.00"),
            mobile_payment_amount=Decimal("150.00"),
            cash_amount=Decimal("0.00"),
            refunded_amount=Decimal("150.00"),
            payment_reference="PAGO-MOBI-01",
            validate=True
        )

        # Assert
        assert settlement.pk is not None
        assert settlement.reimbursement_in_services == Decimal("150.00")

    def test_ID_HP_003_discounts_pure_no_cashflow(self, credit_note_sales_record, credit_note_settlement_factory):
        """Valida una liquidación de descuento puro sin desembolso monetario."""
        # Arrange
        credit_note_sales_record.sale_category = SalesRecord.SaleCategory.GOODS
        credit_note_sales_record.total_sales_inc_vat = Decimal("80.00")
        credit_note_sales_record.save(update_fields=["sale_category", "total_sales_inc_vat"])

        # Act
        settlement = credit_note_settlement_factory(
            sales_record=credit_note_sales_record,
            settlement_type=CreditNoteSettlement.SettlementType.DISCOUNTS,
            returned_goods_value=Decimal("0.00"),
            reimbursement_in_services=Decimal("0.00"),
            commercial_discount_amount=Decimal("80.00"),
            bank_transfer_amount=Decimal("0.00"),
            cash_amount=Decimal("0.00"),
            refunded_amount=Decimal("0.00"),
            payment_reference=None,
            validate=True
        )

        # Assert
        assert settlement.pk is not None
        assert settlement.commercial_discount_amount == Decimal("80.00")
        assert settlement.refunded_amount == Decimal("0.00")

    def test_ID_HP_004_mixed_settlement_mixed_category(self, credit_note_sales_record, credit_note_settlement_factory):
        """Valida una liquidación MIXED combinando devoluciones de bienes, servicios y descuentos."""
        # Arrange
        credit_note_sales_record.sale_category = "MIXED"  # Asumiendo existencia de MIXED en choices
        credit_note_sales_record.total_sales_inc_vat = Decimal("200.00")
        credit_note_sales_record.save(update_fields=["sale_category", "total_sales_inc_vat"])

        # Act
        settlement = credit_note_settlement_factory(
            sales_record=credit_note_sales_record,
            settlement_type=CreditNoteSettlement.SettlementType.MIXED,
            returned_goods_value=Decimal("100.00"),
            reimbursement_in_services=Decimal("50.00"),
            commercial_discount_amount=Decimal("50.00"),
            card_pos_amount=Decimal("150.00"),
            cash_amount=Decimal("0.00"),
            refunded_amount=Decimal("150.00"),
            payment_reference=None,
            validate=True
        )

        # Assert
        assert settlement.pk is not None
        assert settlement.returned_goods_value == Decimal("100.00")
        assert settlement.reimbursement_in_services == Decimal("50.00")

    def test_ID_HP_005_returns_informative_zero_refund(self, credit_note_sales_record, credit_note_settlement_factory):
        """Valida registro informativo de devolución física sin impacto dinerario inmediato."""
        # Arrange
        credit_note_sales_record.sale_category = SalesRecord.SaleCategory.GOODS
        credit_note_sales_record.total_sales_inc_vat = Decimal("120.00")
        credit_note_sales_record.save(update_fields=["sale_category", "total_sales_inc_vat"])

        # Act
        settlement = credit_note_settlement_factory(
            sales_record=credit_note_sales_record,
            settlement_type=CreditNoteSettlement.SettlementType.RETURNS,
            returned_goods_value=Decimal("120.00"),
            reimbursement_in_services=Decimal("0.00"),
            commercial_discount_amount=Decimal("0.00"),
            cash_amount=Decimal("0.00"),
            refunded_amount=Decimal("0.00"),
            payment_reference=None,
            validate=True
        )

        # Assert
        assert settlement.pk is not None
        assert settlement.refunded_amount == Decimal("0.00")

    def test_ID_HP_006_returns_customer_credit_balance(self, credit_note_sales_record, credit_note_settlement_factory):
        """Valida una devolución imputada íntegramente a favor del saldo del cliente."""
        # Arrange
        credit_note_sales_record.sale_category = SalesRecord.SaleCategory.GOODS
        credit_note_sales_record.total_sales_inc_vat = Decimal("300.00")
        credit_note_sales_record.save(update_fields=["sale_category", "total_sales_inc_vat"])

        # Act
        settlement = credit_note_settlement_factory(
            sales_record=credit_note_sales_record,
            settlement_type=CreditNoteSettlement.SettlementType.RETURNS,
            returned_goods_value=Decimal("300.00"),
            customer_credit_balance_amount=Decimal("300.00"),
            cash_amount=Decimal("0.00"),
            refunded_amount=Decimal("300.00"),
            payment_reference=None,
            validate=True
        )

        # Assert
        assert settlement.pk is not None
        assert settlement.customer_credit_balance_amount == Decimal("300.00")


@pytest.mark.django_db
class TestCreditNoteSettlementEdgeCases:
    """Suite de Pruebas Unitarias - Casos Borde y Reglas de Negocio (Edge Cases)."""

    def test_ID_EC_001_denial_invoice_document(self, sales_record, credit_note_settlement_factory):
        """Deniega liquidación vinculada a un documento tipo Factura en vez de Nota de Crédito."""
        # Arrange
        assert sales_record.document_type == SalesRecord.DocumentType.INVOICE

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(sales_record=sales_record, validate=True)

        assert 'sales_record' in exc.value.error_dict

    def test_ID_EC_002_mismatch_operative_breakdown_excess(self, credit_note_sales_record, credit_note_settlement_factory):
        """Rechaza registro cuando el desglose operativo supera el total del documento."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                returned_goods_value=Decimal("80.00"),
                reimbursement_in_services=Decimal("20.00"),
                commercial_discount_amount=Decimal("10.01"),  # Exceso 10.01
                validate=True
            )

        assert '__all__' in exc.value.error_dict

    def test_ID_EC_003_mismatch_operative_breakdown_deficit(self, credit_note_sales_record, credit_note_settlement_factory):
        """Rechaza registro cuando el desglose operativo es menor al total del documento."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                returned_goods_value=Decimal("50.00"),
                commercial_discount_amount=Decimal("49.99"),  # Déficit 0.01
                validate=True
            )

        assert '__all__' in exc.value.error_dict

    def test_ID_EC_004_financial_mismatch(self, credit_note_sales_record, credit_note_settlement_factory):
        """Deniega guardado si la suma de canales monetarios no iguala el monto de refunded_amount."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                settlement_type=CreditNoteSettlement.SettlementType.RETURNS,
                returned_goods_value=Decimal("100.00"),
                bank_transfer_amount=Decimal("30.00"),
                cash_amount=Decimal("20.00"),  # Suma 50
                refunded_amount=Decimal("60.00"),  # No cuadra con 50
                validate=True
            )

        assert 'refunded_amount' in exc.value.error_dict

    def test_ID_EC_005_discount_in_returns(self, credit_note_sales_record, credit_note_settlement_factory):
        """Impide registrar descuentos comerciales en liquidaciones tipo RETURNS."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                settlement_type=CreditNoteSettlement.SettlementType.RETURNS,
                returned_goods_value=Decimal("90.00"),
                commercial_discount_amount=Decimal("10.00"),
                validate=True
            )

        assert 'commercial_discount_amount' in exc.value.error_dict

    def test_ID_EC_006_goods_in_discounts(self, credit_note_sales_record, credit_note_settlement_factory):
        """Impide registrar devolución de bienes en liquidaciones tipo DISCOUNTS."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                settlement_type=CreditNoteSettlement.SettlementType.DISCOUNTS,
                returned_goods_value=Decimal("10.00"),
                commercial_discount_amount=Decimal("90.00"),
                validate=True
            )

        assert 'settlement_type' in exc.value.error_dict

    def test_ID_EC_007_services_in_discounts(self, credit_note_sales_record, credit_note_settlement_factory):
        """Impide registrar devolución de servicios en liquidaciones tipo DISCOUNTS."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                settlement_type=CreditNoteSettlement.SettlementType.DISCOUNTS,
                reimbursement_in_services=Decimal("15.00"),
                commercial_discount_amount=Decimal("85.00"),
                validate=True
            )

        assert 'settlement_type' in exc.value.error_dict

    def test_ID_EC_008_refund_in_discounts(self, credit_note_sales_record, credit_note_settlement_factory):
        """Restringe por completo desembolsos o reembolsos cuando es tipo DISCOUNTS."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                settlement_type=CreditNoteSettlement.SettlementType.DISCOUNTS,
                commercial_discount_amount=Decimal("100.00"),
                cash_amount=Decimal("100.00"),
                refunded_amount=Decimal("100.00"),
                validate=True
            )

        assert 'refunded_amount' in exc.value.error_dict

    def test_ID_EC_009_missing_discount_in_mixed(self, credit_note_sales_record, credit_note_settlement_factory):
        """Exige descuento mayor a cero cuando el tipo es MIXED."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                settlement_type=CreditNoteSettlement.SettlementType.MIXED,
                returned_goods_value=Decimal("100.00"),
                commercial_discount_amount=Decimal("0.00"),
                validate=True
            )

        assert 'settlement_type' in exc.value.error_dict

    def test_ID_EC_010_missing_returns_in_mixed(self, credit_note_sales_record, credit_note_settlement_factory):
        """Exige devoluciones operativas mayores a cero cuando el tipo es MIXED."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                settlement_type=CreditNoteSettlement.SettlementType.MIXED,
                returned_goods_value=Decimal("0.00"),
                reimbursement_in_services=Decimal("0.00"),
                commercial_discount_amount=Decimal("100.00"),
                validate=True
            )

        assert 'settlement_type' in exc.value.error_dict

    def test_ID_EC_011_excess_refund_in_mixed(self, credit_note_sales_record, credit_note_settlement_factory):
        """Impide que el reembolso dinerario supere el valor acumulado de las devoluciones en MIXED."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                settlement_type=CreditNoteSettlement.SettlementType.MIXED,
                returned_goods_value=Decimal("50.00"),
                commercial_discount_amount=Decimal("50.00"),
                cash_amount=Decimal("60.00"),
                refunded_amount=Decimal("60.00"), # Supera 50.00 de bienes
                validate=True
            )

        assert 'refunded_amount' in exc.value.error_dict

    def test_ID_EC_012_goods_returned_in_services_sale(self, credit_note_sales_record, credit_note_settlement_factory):
        """Prohíbe devolución de bienes si la factura de origen es estrictamente de servicios."""
        # Arrange
        credit_note_sales_record.sale_category = SalesRecord.SaleCategory.SERVICES
        credit_note_sales_record.total_sales_inc_vat = Decimal("50.00")
        credit_note_sales_record.save(update_fields=["sale_category", "total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                returned_goods_value=Decimal("50.00"),
                reimbursement_in_services=Decimal("0.00"),
                validate=True
            )

        assert 'returned_goods_value' in exc.value.error_dict

    def test_ID_EC_013_services_reimbursement_in_goods_sale(self, credit_note_sales_record, credit_note_settlement_factory):
        """Prohíbe reversión de servicios si la factura de origen es estrictamente de bienes."""
        # Arrange
        credit_note_sales_record.sale_category = SalesRecord.SaleCategory.GOODS
        credit_note_sales_record.total_sales_inc_vat = Decimal("75.00")
        credit_note_sales_record.save(update_fields=["sale_category", "total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                reimbursement_in_services=Decimal("75.00"),
                returned_goods_value=Decimal("0.00"),
                validate=True
            )

        assert 'reimbursement_in_services' in exc.value.error_dict

    def test_ID_EC_014_missing_bank_transfer_reference(self, credit_note_sales_record, credit_note_settlement_factory):
        """Exige la referencia de pago al asentar desembolso vía transferencia bancaria."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                bank_transfer_amount=Decimal("100.00"),
                cash_amount=Decimal("0.00"),
                payment_reference=None,
                validate=True
            )

        assert 'payment_reference' in exc.value.error_dict

    def test_ID_EC_015_missing_mobile_payment_reference(self, credit_note_sales_record, credit_note_settlement_factory):
        """Exige la referencia de pago al asentar desembolso vía pago móvil."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("40.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                mobile_payment_amount=Decimal("40.00"),
                cash_amount=Decimal("0.00"),
                payment_reference=None,
                validate=True
            )

        assert 'payment_reference' in exc.value.error_dict

    def test_ID_EC_016_blank_payment_reference(self, credit_note_sales_record, credit_note_settlement_factory):
        """Rechaza referencias de pago consistentes solo en espacios en blanco."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("50.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                bank_transfer_amount=Decimal("50.00"),
                cash_amount=Decimal("0.00"),
                payment_reference="   ",
                validate=True
            )

        assert 'payment_reference' in exc.value.error_dict

    def test_ID_EC_017_negative_values_not_allowed(self, credit_note_sales_record, credit_note_settlement_factory):
        """Valida que los valores del desglose no sean negativos."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                returned_goods_value=Decimal("-10.00"),
                validate=True
            )

        assert 'returned_goods_value' in exc.value.error_dict

    def test_ID_EC_018_unique_constraint_per_sales_record(self, credit_note_sales_record, credit_note_settlement_factory):
        """Comprueba restricción única, no debe haber más de una liquidación por Nota de Crédito."""
        # Arrange
        credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
        credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])
        
        credit_note_settlement_factory(
            sales_record=credit_note_sales_record,
            validate=True
        )

        # Act & Assert
        with pytest.raises(IntegrityError):
            credit_note_settlement_factory(
                sales_record=credit_note_sales_record,
                validate=False
            )

    # def test_ID_EC_019_external_modules_isolation(self, account_receivable, credit_note_sales_record, credit_note_settlement_factory):
    #     """Garantiza la invarianza de otros módulos, AccountReceivable no se debe afectar."""
    #     # Arrange
    #     account_receivable.net_receivable_balance = Decimal("500.00")
    #     account_receivable.save(update_fields=["net_receivable_balance"])
        
    #     credit_note_sales_record.total_sales_inc_vat = Decimal("100.00")
    #     credit_note_sales_record.save(update_fields=["total_sales_inc_vat"])

    #     # Act
    #     credit_note_settlement_factory(
    #         sales_record=credit_note_sales_record,
    #         validate=True
    #     )
    #     account_receivable.refresh_from_db()

    #     # Assert
    #     assert account_receivable.net_receivable_balance == Decimal("500.00")

    # def test_ID_EC_020_missing_mandatory_sales_record(self, credit_note_settlement_factory):
    #     """Maneja controladamente el intento de validadción sin un registro base (sales_record=None)."""
    #     # Arrange
    #     # Act & Assert
    #     with pytest.raises(ValidationError) as exc:
    #         credit_note_settlement_factory(
    #             sales_record=None, 
    #             validate=True
    #         )

    #     # Validar que el error atrapado corresponda a la nulidad de la relación principal
    #     assert exc.value is not None