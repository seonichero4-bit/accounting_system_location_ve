"""Suite de pruebas unitarias para la propiedad base_receivable_balance.

Implementa los casos de prueba definidos en el Plan de Pruebas Unitario,
evaluando los flujos felices y casos borde de la ecuación base de la CxC.
"""

from decimal import Decimal
from typing import Callable

import pytest

from data_access.models.customer_payment import CustomerPayment
from data_access.models.payment_imputation import PaymentImputation
from data_access.models.sales_record import SalesRecord
from data_access.models.vat_withholding_sales import VatWithHolding
from data_access.models.islr_withholding_sales import IslrWithHolding


@pytest.mark.django_db
def test_ID_HP_001_base_balance_no_retentions_no_payments(
    sales_record: SalesRecord
) -> None:
    """[ID_HP_001] Validar que el saldo base sea idéntico al monto total facturado
    cuando no hay retenciones fiscales ni imputaciones de pago.
    """
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("1000.00")
    sales_record.save(update_fields=['total_sales_inc_vat'])
    
    ar = sales_record.account_receivable

    # Act
    balance = ar.base_receivable_balance

    # Assert
    assert balance == Decimal("1000.00")


@pytest.mark.django_db
def test_ID_HP_002_base_balance_only_withholdings(
    sales_record: SalesRecord,
    vat_withholding: VatWithHolding,
    islr_withholding: IslrWithHolding
) -> None:
    """[ID_HP_002] Validar que el saldo base deduzca correctamente los montos
    retenidos por IVA e ISLR asociados a la factura originaria sin pagos.
    """
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("1000.00")
    sales_record.save(update_fields=['total_sales_inc_vat'])
    
    vat_withholding.withheld_amount = Decimal("160.00")
    vat_withholding.save(update_fields=['withheld_amount'])
    
    islr_withholding.total_withheld_amount = Decimal("30.00")
    islr_withholding.save(update_fields=['total_withheld_amount'])
    
    ar = sales_record.account_receivable

    # Act
    balance = ar.base_receivable_balance

    # Assert
    assert balance == Decimal("810.00")


@pytest.mark.django_db
def test_ID_HP_003_base_balance_only_payments(
    sales_record: SalesRecord,
    customer_payment_factory: Callable[..., CustomerPayment],
    payment_imputation_factory: Callable[..., PaymentImputation]
) -> None:
    """[ID_HP_003] Validar que el saldo base deduzca las imputaciones de pago
    directas registradas sobre la cuenta por cobrar en ausencia de retenciones.
    """
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("1000.00")
    sales_record.save(update_fields=['total_sales_inc_vat'])
    
    ar = sales_record.account_receivable
    
    payment = customer_payment_factory(total_amount=Decimal("400.00"))
    payment_imputation_factory(
        payment=payment,
        account_receivable=ar,
        imputed_amount=Decimal("400.00")
    )

    # Act
    balance = ar.base_receivable_balance

    # Assert
    assert balance == Decimal("600.00")


@pytest.mark.django_db
def test_ID_HP_004_base_balance_withholdings_and_payments(
    sales_record: SalesRecord,
    vat_withholding: VatWithHolding,
    islr_withholding: IslrWithHolding,
    customer_payment_factory: Callable[..., CustomerPayment],
    payment_imputation_factory: Callable[..., PaymentImputation]
) -> None:
    """[ID_HP_004] Validar la consolidación aritmética completa deduciendo 
    retenciones e imputaciones de pago al valor total de la venta.
    """
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("1500.00")
    sales_record.save(update_fields=['total_sales_inc_vat'])
    
    vat_withholding.withheld_amount = Decimal("120.00")
    vat_withholding.save(update_fields=['withheld_amount'])
    
    islr_withholding.total_withheld_amount = Decimal("45.00")
    islr_withholding.save(update_fields=['total_withheld_amount'])
    
    ar = sales_record.account_receivable
    
    payment = customer_payment_factory(total_amount=Decimal("335.00"))
    payment_imputation_factory(
        payment=payment,
        account_receivable=ar,
        imputed_amount=Decimal("335.00")
    )

    # Act
    balance = ar.base_receivable_balance

    # Assert
    assert balance == Decimal("1000.00")


@pytest.mark.django_db
def test_ID_HP_005_base_balance_exact_cancellation(
    sales_record: SalesRecord,
    vat_withholding: VatWithHolding,
    customer_payment_factory: Callable[..., CustomerPayment],
    payment_imputation_factory: Callable[..., PaymentImputation]
) -> None:
    """[ID_HP_005] Validar que cuando las retenciones y pagos cubren exactamente 
    el valor total de la factura originaria, el saldo devuelto sea cero.
    """
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("500.00")
    sales_record.save(update_fields=['total_sales_inc_vat'])
    
    vat_withholding.withheld_amount = Decimal("75.00")
    vat_withholding.save(update_fields=['withheld_amount'])
    
    ar = sales_record.account_receivable
    
    payment = customer_payment_factory(total_amount=Decimal("425.00"))
    payment_imputation_factory(
        payment=payment,
        account_receivable=ar,
        imputed_amount=Decimal("425.00")
    )

    # Act
    balance = ar.base_receivable_balance

    # Assert
    assert balance == Decimal("0.00")


@pytest.mark.django_db
def test_ID_EC_001_base_balance_ignores_credit_debit_notes(
    sales_record: SalesRecord,
    credit_note_sales_record: SalesRecord
) -> None:
    """[ID_EC_001] Verificar que la propiedad ignore deliberadamente el impacto de 
    notas de crédito o débito vinculadas a la factura.
    """
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("1000.00")
    sales_record.save(update_fields=['total_sales_inc_vat'])
    
    # 1. Nota de crédito (existente por fixture, se actualiza el monto)
    credit_note_sales_record.total_sales_inc_vat = Decimal("300.00")
    credit_note_sales_record.save(update_fields=['total_sales_inc_vat'])
    
    # 2. Nota de débito asociada a la factura originaria
    SalesRecord.objects.create(
        fiscal_profile=sales_record.fiscal_profile,
        client=sales_record.client,
        fiscal_period=sales_record.fiscal_period,
        document_date=sales_record.document_date,
        document_type=SalesRecord.DocumentType.DEBIT_NOTE,
        transaction_type=SalesRecord.TransactionType.ADJUSTMENT,
        sale_type=SalesRecord.SaleType.INTERNAL,
        record_status=SalesRecord.RecordStatus.PRELIMINARY,
        document_number="00000003",
        control_number="00-00000003",
        affected_invoice=sales_record,
        total_sales_inc_vat=Decimal("200.00")
    )
    
    ar = sales_record.account_receivable

    # Act
    balance = ar.base_receivable_balance

    # Assert
    assert balance == Decimal("1000.00")


@pytest.mark.django_db
def test_ID_EC_002_base_balance_excludes_note_withholdings(
    sales_record: SalesRecord,
    credit_note_sales_record: SalesRecord,
    vat_withholding: VatWithHolding
) -> None:
    """[ID_EC_002] Garantizar que la consulta filtre únicamente las retenciones 
    vinculadas de forma directa al documento de venta principal y no a sus notas asociadas.
    """
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("500.00")
    sales_record.save(update_fields=['total_sales_inc_vat'])
    
    vat_withholding.withheld_amount = Decimal("50.00")
    vat_withholding.save(update_fields=['withheld_amount'])
    
    # Crear retención (20.00) vinculada estrictamente a la Nota de Crédito
    VatWithHolding.objects.create(
        fiscal_profile=vat_withholding.fiscal_profile,
        voucher_number="20260100000002",
        issue_date=vat_withholding.issue_date,
        fiscal_period=vat_withholding.fiscal_period,
        client_name=vat_withholding.client_name,
        client_rif=vat_withholding.client_rif,
        document_number=credit_note_sales_record.document_number,
        control_number=credit_note_sales_record.control_number,
        total_amount=Decimal("20.00"),
        tax_base=Decimal("20.00"),
        tax_caused=Decimal("3.20"),
        withheld_amount=Decimal("20.00"),
        client=vat_withholding.client,
        document=credit_note_sales_record
    )
    
    ar = sales_record.account_receivable

    # Act
    balance = ar.base_receivable_balance

    # Assert
    # Solo debe deducir los 50.00 correspondientes al documento principal
    assert balance == Decimal("450.00")