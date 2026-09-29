"""Módulo de pruebas unitarias para la propiedad net_receivable_balance de AccountReceivable.

Valida la exactitud del cálculo del saldo neto exigible consolidando facturas base,
retenciones de IVA e ISLR, notas de débito, notas de crédito, imputaciones de pago y
desembolsos por liquidación de notas de crédito.
"""

from decimal import Decimal
from typing import Callable

import pytest

from data_access.models.account_receivable import AccountReceivable
from data_access.models.sales_record import SalesRecord


@pytest.mark.django_db
def test_id_hp_001_net_receivable_balance_simple_invoice(
    sales_record_factory: Callable,
) -> None:
    """[ID_HP_001] Validar el saldo neto de una factura base simple sin vinculaciones."""
    # Arrange
    sales_record = sales_record_factory(
        total_sales_inc_vat=Decimal("1000.00")
    )
    account_receivable: AccountReceivable = sales_record.account_receivable

    # Act
    balance = account_receivable.net_receivable_balance

    # Assert
    assert balance == Decimal("1000.00")


@pytest.mark.django_db
def test_id_hp_002_net_receivable_balance_with_direct_retentions(
    sales_record_factory: Callable,
    vat_withholding_factory: Callable,
    islr_withholding_factory: Callable,
) -> None:
    """[ID_HP_002] Verificar deducción de retenciones originarias de IVA e ISLR."""
    # Arrange
    sales_record = sales_record_factory(
        total_sales_inc_vat=Decimal("1000.00")
    )
    account_receivable: AccountReceivable = sales_record.account_receivable

    vat_withholding_factory(
        document=sales_record,
        withheld_amount=Decimal("120.00")
    )
    islr_withholding_factory(
        document=sales_record,
        total_withheld_amount=Decimal("20.00")
    )

    # Act
    balance = account_receivable.net_receivable_balance

    # Assert
    assert balance == Decimal("860.00")


@pytest.mark.django_db
def test_id_hp_003_net_receivable_balance_with_payment_imputation(
    sales_record_factory: Callable,
    payment_imputation_factory: Callable,
) -> None:
    """[ID_HP_003] Validar amortización por una imputación de pago directa."""
    # Arrange
    sales_record = sales_record_factory(
        total_sales_inc_vat=Decimal("1000.00")
    )
    account_receivable: AccountReceivable = sales_record.account_receivable

    payment_imputation_factory(
        account_receivable=account_receivable,
        imputed_amount=Decimal("400.00")
    )

    # Act
    balance = account_receivable.net_receivable_balance

    # Assert
    assert balance == Decimal("600.00")


@pytest.mark.django_db
def test_id_hp_004_net_receivable_balance_increased_by_debit_note(
    sales_record_factory: Callable,
) -> None:
    """[ID_HP_004] Verificar que una Nota de Débito incrementa el saldo exigible."""
    # Arrange
    base_invoice = sales_record_factory(
        total_sales_inc_vat=Decimal("1000.00")
    )
    account_receivable: AccountReceivable = base_invoice.account_receivable

    sales_record_factory(
        document_type=SalesRecord.DocumentType.DEBIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("200.00")
    )

    # Act
    balance = account_receivable.net_receivable_balance

    # Assert
    assert balance == Decimal("1200.00")


@pytest.mark.django_db
def test_id_hp_005_net_receivable_balance_reduced_by_credit_note(
    sales_record_factory: Callable,
) -> None:
    """[ID_HP_005] Verificar que una Nota de Crédito disminuye el saldo exigible."""
    # Arrange
    base_invoice = sales_record_factory(
        total_sales_inc_vat=Decimal("1000.00")
    )
    account_receivable: AccountReceivable = base_invoice.account_receivable

    sales_record_factory(
        document_type=SalesRecord.DocumentType.CREDIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("300.00")
    )

    # Act
    balance = account_receivable.net_receivable_balance

    # Assert
    assert balance == Decimal("700.00")


@pytest.mark.django_db
def test_id_hp_006_net_receivable_balance_with_credit_note_settlement_reimbursement(
    sales_record_factory: Callable,
    payment_imputation_factory: Callable,
    credit_note_settlement_factory: Callable,
) -> None:
    """[ID_HP_006] Validar reincorporación al saldo por liquidación de Nota de Crédito."""
    # Arrange
    base_invoice = sales_record_factory(
        total_sales_inc_vat=Decimal("1000.00")
    )
    account_receivable: AccountReceivable = base_invoice.account_receivable

    payment_imputation_factory(
        account_receivable=account_receivable,
        imputed_amount=Decimal("1000.00")
    )
    credit_note = sales_record_factory(
        document_type=SalesRecord.DocumentType.CREDIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("200.00")
    )
    credit_note_settlement_factory(
        sales_record=credit_note,
        refunded_amount=Decimal("200.00")
    )

    # Act
    balance = account_receivable.net_receivable_balance

    # Assert
    assert balance == Decimal("0.00")


@pytest.mark.django_db
def test_id_hp_007_net_receivable_balance_multivariable_integration(
    sales_record_factory: Callable,
    vat_withholding_factory: Callable,
    payment_imputation_factory: Callable,
    credit_note_settlement_factory: Callable,
) -> None:
    """[ID_HP_007] Evaluar la precisión algebraica consolidando todas las variables."""
    # Arrange
    base_invoice = sales_record_factory(
        total_sales_inc_vat=Decimal("2000.00")
    )
    account_receivable: AccountReceivable = base_invoice.account_receivable

    vat_withholding_factory(
        document=base_invoice,
        withheld_amount=Decimal("240.00")
    )

    debit_note = sales_record_factory(
        document_type=SalesRecord.DocumentType.DEBIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("500.00")
    )
    vat_withholding_factory(
        document=debit_note,
        withheld_amount=Decimal("60.00")
    )

    payment_imputation_factory(
        account_receivable=account_receivable,
        imputed_amount=Decimal("2200.00")
    )

    credit_note = sales_record_factory(
        document_type=SalesRecord.DocumentType.CREDIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("300.00")
    )
    vat_withholding_factory(
        document=credit_note,
        withheld_amount=Decimal("36.00")
    )

    credit_note_settlement_factory(
        sales_record=credit_note,
        refunded_amount=Decimal("264.00")
    )

    # Act
    balance = account_receivable.net_receivable_balance

    # Assert
    assert balance == Decimal("0.00")


@pytest.mark.django_db
def test_id_ec_001_net_receivable_balance_exact_zero_on_full_payment(
    sales_record_factory: Callable,
    payment_imputation_factory: Callable,
) -> None:
    """[ID_EC_001] Verificar exactitud decimal al liquidar completamente la deuda."""
    # Arrange
    base_invoice = sales_record_factory(
        total_sales_inc_vat=Decimal("500.00")
    )
    account_receivable: AccountReceivable = base_invoice.account_receivable

    payment_imputation_factory(
        account_receivable=account_receivable,
        imputed_amount=Decimal("500.00")
    )

    # Act
    balance = account_receivable.net_receivable_balance

    # Assert
    assert balance == Decimal("0.00")


@pytest.mark.django_db
def test_id_ec_002_net_receivable_balance_negative_credit_balance(
    sales_record_factory: Callable,
    payment_imputation_factory: Callable,
) -> None:
    """[ID_EC_002] Verificar retorno de saldo negativo cuando existe crédito a favor."""
    # Arrange
    base_invoice = sales_record_factory(
        total_sales_inc_vat=Decimal("1000.00")
    )
    account_receivable: AccountReceivable = base_invoice.account_receivable

    payment_imputation_factory(
        account_receivable=account_receivable,
        imputed_amount=Decimal("1000.00")
    )
    sales_record_factory(
        document_type=SalesRecord.DocumentType.CREDIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("400.00")
    )

    # Act
    balance = account_receivable.net_receivable_balance

    # Assert
    assert balance == Decimal("-400.00")


@pytest.mark.django_db
def test_id_ec_003_net_receivable_balance_multiple_credit_and_debit_notes(
    sales_record_factory: Callable,
) -> None:
    """[ID_EC_003] Validar agregación con múltiples notas de crédito y débito."""
    # Arrange
    base_invoice = sales_record_factory(
        total_sales_inc_vat=Decimal("5000.00")
    )
    account_receivable: AccountReceivable = base_invoice.account_receivable

    sales_record_factory(
        document_type=SalesRecord.DocumentType.CREDIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("500.00")
    )
    sales_record_factory(
        document_type=SalesRecord.DocumentType.CREDIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("300.00")
    )
    sales_record_factory(
        document_type=SalesRecord.DocumentType.CREDIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("200.00")
    )

    sales_record_factory(
        document_type=SalesRecord.DocumentType.DEBIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("150.00")
    )
    sales_record_factory(
        document_type=SalesRecord.DocumentType.DEBIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("250.00")
    )

    # Act
    balance = account_receivable.net_receivable_balance

    # Assert
    assert balance == Decimal("4400.00")


@pytest.mark.django_db
def test_id_ec_004_net_receivable_balance_multiple_fragmented_imputations(
    sales_record_factory: Callable,
    payment_imputation_factory: Callable,
) -> None:
    """[ID_EC_004] Verificar precisión contable con múltiples amortizaciones decimales."""
    # Arrange
    base_invoice = sales_record_factory(
        total_sales_inc_vat=Decimal("1500.00")
    )
    account_receivable: AccountReceivable = base_invoice.account_receivable

    payment_imputation_factory(
        account_receivable=account_receivable,
        imputed_amount=Decimal("100.25")
    )
    payment_imputation_factory(
        account_receivable=account_receivable,
        imputed_amount=Decimal("200.50")
    )
    payment_imputation_factory(
        account_receivable=account_receivable,
        imputed_amount=Decimal("300.25")
    )
    payment_imputation_factory(
        account_receivable=account_receivable,
        imputed_amount=Decimal("399.00")
    )

    # Act
    balance = account_receivable.net_receivable_balance

    # Assert
    assert balance == Decimal("500.00")


@pytest.mark.django_db
def test_id_ec_005_net_receivable_balance_multiple_credit_note_settlements(
    sales_record_factory: Callable,
    payment_imputation_factory: Callable,
    credit_note_settlement_factory: Callable,
) -> None:
    """[ID_EC_005] Probar liquidaciones múltiples con reembolsos parciales acumulados."""
    # Arrange
    base_invoice = sales_record_factory(
        total_sales_inc_vat=Decimal("2000.00")
    )
    account_receivable: AccountReceivable = base_invoice.account_receivable

    payment_imputation_factory(
        account_receivable=account_receivable,
        imputed_amount=Decimal("2000.00")
    )

    nc1 = sales_record_factory(
        document_type=SalesRecord.DocumentType.CREDIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("300.00")
    )
    nc2 = sales_record_factory(
        document_type=SalesRecord.DocumentType.CREDIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("200.00")
    )

    credit_note_settlement_factory(
        sales_record=nc1,
        refunded_amount=Decimal("300.00")
    )
    credit_note_settlement_factory(
        sales_record=nc2,
        refunded_amount=Decimal("200.00")
    )

    # Act
    balance = account_receivable.net_receivable_balance

    # Assert
    assert balance == Decimal("0.00")


@pytest.mark.django_db
def test_id_ec_006_net_receivable_balance_decimal_precision_extreme_fractions(
    sales_record_factory: Callable,
    vat_withholding_factory: Callable,
    islr_withholding_factory: Callable,
    payment_imputation_factory: Callable,
    credit_note_settlement_factory: Callable,
) -> None:
    """[ID_EC_006] Garantizar exactitud sin errores de redondeo en decimales complejos."""
    # Arrange
    base_invoice = sales_record_factory(
        total_sales_inc_vat=Decimal("1000.33")
    )
    account_receivable: AccountReceivable = base_invoice.account_receivable

    vat_withholding_factory(
        document=base_invoice,
        withheld_amount=Decimal("120.05")
    )
    islr_withholding_factory(
        document=base_invoice,
        total_withheld_amount=Decimal("20.01")
    )

    payment_imputation_factory(
        account_receivable=account_receivable,
        imputed_amount=Decimal("860.27")
    )

    credit_note = sales_record_factory(
        document_type=SalesRecord.DocumentType.CREDIT_NOTE,
        affected_invoice=base_invoice,
        total_sales_inc_vat=Decimal("100.08")
    )
    credit_note_settlement_factory(
        sales_record=credit_note,
        refunded_amount=Decimal("100.08")
    )

    # Act
    balance = account_receivable.net_receivable_balance

    # Assert
    assert balance == Decimal("0.00")


@pytest.mark.django_db
def test_id_ec_007_net_receivable_balance_cross_tenant_isolation(
    sales_record_factory: Callable,
    payment_imputation_factory: Callable,
) -> None:
    """[ID_EC_007] Verificar aislamiento estricto de notas e imputaciones entre facturas."""
    # Arrange
    invoice_a = sales_record_factory(
        total_sales_inc_vat=Decimal("1000.00")
    )
    account_receivable_a: AccountReceivable = invoice_a.account_receivable

    invoice_b = sales_record_factory(
        total_sales_inc_vat=Decimal("5000.00")
    )
    account_receivable_b: AccountReceivable = invoice_b.account_receivable

    sales_record_factory(
        document_type=SalesRecord.DocumentType.CREDIT_NOTE,
        affected_invoice=invoice_b,
        total_sales_inc_vat=Decimal("2000.00")
    )
    payment_imputation_factory(
        account_receivable=account_receivable_b,
        imputed_amount=Decimal("1000.00")
    )

    # Act
    balance_a = account_receivable_a.net_receivable_balance

    # Assert
    assert balance_a == Decimal("1000.00")


@pytest.mark.django_db
def test_id_ec_008_net_receivable_balance_isolation_from_other_credit_note_settlements(
    sales_record_factory: Callable,
    credit_note_settlement_factory: Callable,
) -> None:
    """[ID_EC_008] Validar que liquidaciones de otras facturas no alteren el saldo."""
    # Arrange
    invoice_a = sales_record_factory(
        total_sales_inc_vat=Decimal("1000.00")
    )
    account_receivable_a: AccountReceivable = invoice_a.account_receivable

    invoice_b = sales_record_factory(
        total_sales_inc_vat=Decimal("5000.00")
    )
    nc_b = sales_record_factory(
        document_type=SalesRecord.DocumentType.CREDIT_NOTE,
        affected_invoice=invoice_b,
        total_sales_inc_vat=Decimal("1000.00")
    )
    credit_note_settlement_factory(
        sales_record=nc_b,
        refunded_amount=Decimal("500.00")
    )

    # Act
    balance_a = account_receivable_a.net_receivable_balance

    # Assert
    assert balance_a == Decimal("1000.00")