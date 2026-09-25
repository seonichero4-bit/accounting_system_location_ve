"""Suite de pruebas unitarias para la capa de datos (Modelos).

Contiene los casos de prueba detallados en el plan de pruebas para las
entidades CustomerPayment, AccountReceivable, PaymentImputation y sus 
respectivas propiedades matemáticas y de validación.
"""

from decimal import Decimal
from typing import Callable

import pytest
from django.core.exceptions import ValidationError

from data_access.models.account_receivable import AccountReceivable, AccountReceivableStatusChoices
from data_access.models.customer_payment import CustomerPayment
from data_access.models.payment_imputation import PaymentImputation
from data_access.models.sales_record import SalesRecord
from data_access.models.vat_withholding_sales import VatWithHolding
from data_access.models.islr_withholding_sales import IslrWithHolding


@pytest.mark.django_db
def test_ID_HP_001_create_customer_payment_ves_exact_match(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable],
    customer_payment_factory: Callable[..., CustomerPayment],
    payment_imputation_factory: Callable[..., PaymentImputation]
) -> None:
    """Verifica el registro de un pago en moneda local (VES) con cuadre exacto."""
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("500.00")
    sales_record.save()
    ar = account_receivable_factory(sales_record=sales_record)
    
    payment = customer_payment_factory(
        currency="VES",
        total_amount=Decimal("300.00")
    )
    payment_imputation_factory(
        payment=payment,
        account_receivable=ar,
        imputed_amount=Decimal("300.00")
    )

    # Act
    payment.full_clean()

    # Assert
    assert payment.total_amount == sum(
        imp.imputed_amount for imp in payment.imputations.all()
    )


@pytest.mark.django_db
def test_ID_HP_002_create_customer_payment_usd_valid_rate(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable],
    customer_payment_factory: Callable[..., CustomerPayment],
    payment_imputation_factory: Callable[..., PaymentImputation]
) -> None:
    """Validar que los pagos en divisas permitan persistir con cuadre exacto y tasa válida."""
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("500.00")
    sales_record.save()
    ar = account_receivable_factory(sales_record=sales_record)
    
    payment = customer_payment_factory(
        currency="USD",
        exchange_rate=Decimal("36.5000"),
        total_amount=Decimal("100.00")
    )
    payment_imputation_factory(
        payment=payment,
        account_receivable=ar,
        imputed_amount=Decimal("100.00")
    )

    # Act
    payment.full_clean()

    # Assert
    assert payment.total_amount == Decimal("100.00")
    assert payment.exchange_rate > Decimal("0.0000")


@pytest.mark.django_db
def test_ID_HP_003_convert_and_impute_foreign_payment_in_ves(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable],
    customer_payment_factory: Callable[..., CustomerPayment],
    payment_imputation_factory: Callable[..., PaymentImputation]
) -> None:
    """Validar el cálculo y la imputación a la CxC en moneda nacional de un pago en divisas."""
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("5000.00")
    sales_record.save()
    ar = account_receivable_factory(sales_record=sales_record)
    
    # 100.00 USD * 36.5000 = 3650.00 VES
    payment = customer_payment_factory(
        currency="USD",
        nominal_value=Decimal("100.00"),
        exchange_rate=Decimal("36.5000"),
        total_amount=Decimal("3650.00")
    )
    payment_imputation_factory(
        payment=payment,
        account_receivable=ar,
        imputed_amount=Decimal("3650.00")
    )

    # Act
    payment.full_clean()

    # Assert
    assert payment.total_amount == Decimal("3650.00")


@pytest.mark.django_db
def test_ID_HP_004_valid_imputation_within_balance_limit(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable],
    customer_payment_factory: Callable[..., CustomerPayment],
    payment_imputation_factory: Callable[..., PaymentImputation]
) -> None:
    """Validar asignación de pago parcial menor o igual al saldo exigible."""
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("500.00")
    sales_record.save()
    ar = account_receivable_factory(sales_record=sales_record)
    payment = customer_payment_factory(total_amount=Decimal("400.00"))
    
    imputation = payment_imputation_factory(
        payment=payment,
        account_receivable=ar,
        imputed_amount=Decimal("400.00")
    )

    # Act
    imputation.full_clean()

    # Assert
    assert imputation.imputed_amount <= (ar.net_receivable_balance + imputation.imputed_amount)


@pytest.mark.django_db
def test_ID_EC_001_mark_ar_paid_with_pending_balance(
    account_receivable_factory: Callable[..., AccountReceivable]
) -> None:
    """Forzar cambio de estado a PAID con saldo exigible pendiente."""
    # Arrange
    ar = account_receivable_factory()  # Por defecto tiene saldo > 0
    ar.status = "PAID"

    # Act & Assert
    with pytest.raises(ValidationError, match="No se puede marcar la cuenta por cobrar como pagada porque aún posee un saldo neto exigible pendiente."):
        ar.full_clean()


@pytest.mark.django_db
def test_ID_EC_002(account_receivable_factory):
    """Verifica que se bloquee cualquier intento de modificación sobre una CxC anulada."""
    # Arrange: Se simula la existencia previa de una cuenta por cobrar en estado ANNULLED
    ar = account_receivable_factory()
    ar.status = AccountReceivableStatusChoices.ANNULLED
    ar.save(update_fields=['status'])  # Se persiste el estado para evitar llamar clean() durante la configuración

    # Act: Se intenta modificar un atributo sobre la instancia 'ar' ya anulada
    ar.fiscal_period = ar.fiscal_period.replace(year=ar.fiscal_period.year + 1)

    # Assert: La validación debe reaccionar al intento de modificación sobre el registro anulado
    with pytest.raises(ValidationError) as exc_info:
        ar.full_clean()

    assert 'status' in exc_info.value.message_dict
    assert "No se pueden realizar operaciones sobre una cuenta por cobrar que se encuentra anulada." in exc_info.value.message_dict['status']


@pytest.mark.django_db
def test_ID_EC_003_ar_unique_violation_per_document_and_profile(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable]
) -> None:
    """Intentar duplicar la CxC para una misma venta en el mismo perfil fiscal."""
    # Arrange
    account_receivable_factory(sales_record=sales_record)

    # Act & Assert
    with pytest.raises(
        ValidationError,
        match="Ya existe Account Receivable con este Sales Record."
    ):
        account_receivable_factory(sales_record=sales_record)


@pytest.mark.django_db
def test_ID_EC_004_financial_mismatch_payment_and_imputations(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable],
    customer_payment_factory: Callable[..., CustomerPayment],
    payment_imputation_factory: Callable[..., PaymentImputation]
) -> None:
    """Disparar fallo cuando la suma de imputaciones difiere de total_amount."""
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("1000.00")
    sales_record.save()
    ar1 = account_receivable_factory(sales_record=sales_record)

    # Segunda CxC basada en otra factura para no duplicar la relación OneToOne ni la restricción de unicidad
    sales_record_2 = SalesRecord.objects.create(
        fiscal_profile=sales_record.fiscal_profile,
        client=sales_record.client,
        fiscal_period=sales_record.fiscal_period,
        document_date=sales_record.document_date,
        document_type=sales_record.document_type,
        transaction_type=sales_record.transaction_type,
        sale_type=sales_record.sale_type,
        record_status=sales_record.record_status,
        document_number="00000002",
        control_number="00-00000002",
        general_tax_base_16=Decimal("500.00"),
        general_tax_debit_16=Decimal("80.00"),
        total_sales_inc_vat=Decimal("580.00")
    )
    ar2 = account_receivable_factory(sales_record=sales_record_2)

    payment = customer_payment_factory(total_amount=Decimal("500.00"))

    # Imputaciones suman 450.00 (250.00 + 200.00) y difieren de los 500.00 del pago
    payment_imputation_factory(payment=payment, account_receivable=ar1, imputed_amount=Decimal("250.00"))
    payment_imputation_factory(payment=payment, account_receivable=ar2, imputed_amount=Decimal("200.00"))

    # Act & Assert
    with pytest.raises(
        ValidationError, 
        match="El monto total reportado en el pago no coincide con la sumatoria de los montos imputados a las cuentas por cobrar."
    ):
        payment.full_clean()


@pytest.mark.django_db
def test_ID_EC_005_payment_amount_less_or_equal_to_zero(
    customer_payment_factory: Callable[..., CustomerPayment]
) -> None:
    """Validar que no se permitan montos de cobro nulos o negativos."""
    # Arrange
    payment = customer_payment_factory(
        nominal_value=Decimal("-10.00"),
        total_amount=Decimal("-10.00")
    )

    # Act & Assert
    with pytest.raises(ValidationError, match="El monto total del pago debe ser mayor a cero."):
        payment.full_clean()


@pytest.mark.django_db
def test_ID_EC_006_imputed_amount_exceeds_net_balance(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable],
    customer_payment_factory: Callable[..., CustomerPayment],
    payment_imputation_factory: Callable[..., PaymentImputation]
) -> None:
    """Intentar amortizar un valor mayor al saldo disponible actual."""
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("500.00")
    sales_record.save()
    ar = account_receivable_factory(sales_record=sales_record)
    
    payment = customer_payment_factory(total_amount=Decimal("800.00"))

    # Act & Assert
    with pytest.raises(ValidationError, match=r"El monto a imputar excede el saldo neto exigible vigente \(500\.00\) de la cuenta por cobrar seleccionada\."):
        payment_imputation_factory(
            payment=payment,
            account_receivable=ar,
            imputed_amount=Decimal("800.00")
        )


@pytest.mark.django_db
def test_ID_EC_007_duplicate_imputation_same_payment_and_ar(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable],
    customer_payment_factory: Callable[..., CustomerPayment],
    payment_imputation_factory: Callable[..., PaymentImputation]
) -> None:
    """Evitar que una misma CxC sea asociada múltiples veces al mismo pago."""
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("1000.00")
    sales_record.save()
    ar = account_receivable_factory(sales_record=sales_record)
    payment = customer_payment_factory(total_amount=Decimal("200.00"))
    
    payment_imputation_factory(
        payment=payment,
        account_receivable=ar,
        imputed_amount=Decimal("100.00")
    )

    # Act & Assert
    with pytest.raises(ValidationError, match="No se puede imputar más de una vez el mismo pago a la misma cuenta por cobrar."):
        payment_imputation_factory(
            payment=payment,
            account_receivable=ar,
            imputed_amount=Decimal("100.00")
        )


@pytest.mark.django_db
def test_ID_EC_008_imputed_amount_less_or_equal_to_zero(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable],
    customer_payment_factory: Callable[..., CustomerPayment],
    payment_imputation_factory: Callable[..., PaymentImputation]
) -> None:
    """Controlar que no se procesen imputaciones con valores cero o negativos."""
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("500.00")
    sales_record.save()
    ar = account_receivable_factory(sales_record=sales_record)
    payment = customer_payment_factory(total_amount=Decimal("0.00"))

    # Act & Assert
    with pytest.raises(ValidationError, match="El monto a imputar debe ser un valor positivo mayor a cero."):
        payment_imputation_factory(
            payment=payment,
            account_receivable=ar,
            imputed_amount=Decimal("-5.00")
        )


# --- PRUEBAS PARA PROPIEDADES MATEMÁTICAS ---

@pytest.mark.django_db
def test_ID_HP_001_net_retention_multiple_withholdings(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable],
    vat_withholding: VatWithHolding,
    islr_withholding: IslrWithHolding
) -> None:
    """Validación de accumulated_net_retention con múltiples retenciones originarias."""
    # Arrange
    vat_withholding.withheld_amount = Decimal("15.50")
    vat_withholding.save()

    islr_withholding.total_withheld_amount = Decimal("5.25")
    islr_withholding.save()

    ar = account_receivable_factory(sales_record=sales_record)

    # Act
    net_retention = ar.accumulated_net_retention

    # Assert
    assert net_retention == Decimal("20.75")


@pytest.mark.django_db
def test_ID_HP_002_net_retention_with_adjustments(
    sales_record: SalesRecord,
    credit_note_sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable],
    vat_withholding: VatWithHolding
) -> None:
    """Validación de accumulated_net_retention con retenciones y ajustes."""
    # Arrange
    # vat_withholding.withheld_amount = Decimal("100.00")
    # vat_withholding.save()

    # Creación de ajuste negativo manual asociado al documento de ajuste (Nota de Crédito)
    VatWithHolding.objects.create(
        fiscal_profile=vat_withholding.fiscal_profile,
        voucher_number="20260100000002",
        issue_date=vat_withholding.issue_date,
        fiscal_period=vat_withholding.fiscal_period,
        client_name=vat_withholding.client_name,
        client_rif=vat_withholding.client_rif,
        document_number=credit_note_sales_record.document_number,
        control_number=credit_note_sales_record.control_number,
        total_amount=Decimal("10.00"),
        tax_base=Decimal("10.00"),
        tax_caused=Decimal("1.60"),
        withheld_amount=Decimal("1.20"),
        client=vat_withholding.client,
        document=credit_note_sales_record
    )

    ar = account_receivable_factory(sales_record=sales_record)

    # Act
    net_retention = ar.accumulated_net_retention

    # Assert
    assert net_retention == Decimal("10.80")

@pytest.mark.django_db
def test_ID_HP_003_net_balance_no_retentions_no_imputations(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable]
) -> None:
    """Cálculo de net_receivable_balance sin retenciones ni pagos aplicados."""
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("500.00")
    sales_record.save()
    
    ar = account_receivable_factory(sales_record=sales_record)

    # Act
    balance = ar.net_receivable_balance

    # Assert
    assert balance == Decimal("500.00")


@pytest.mark.django_db
def test_ID_HP_004_net_balance_with_retentions_and_payments(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable],
    customer_payment_factory: Callable[..., CustomerPayment],
    payment_imputation_factory: Callable[..., PaymentImputation],
    vat_withholding: VatWithHolding
) -> None:
    """Cálculo del saldo exigible en tiempo real tras retenciones e imputaciones."""
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("1000.00")
    sales_record.save()
    
    vat_withholding.withheld_amount = Decimal("150.00")
    vat_withholding.save()
    
    ar = account_receivable_factory(sales_record=sales_record)
    
    payment = customer_payment_factory(total_amount=Decimal("300.00"))
    payment_imputation_factory(
        payment=payment,
        account_receivable=ar,
        imputed_amount=Decimal("300.00")
    )

    # Act
    balance = ar.net_receivable_balance

    # Assert
    assert balance == Decimal("550.00")


@pytest.mark.django_db
def test_ID_HP_005_net_balance_fully_paid(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable],
    customer_payment_factory: Callable[..., CustomerPayment],
    payment_imputation_factory: Callable[..., PaymentImputation],
    vat_withholding: VatWithHolding
) -> None:
    """Verificación del balance cuando retenciones e imputaciones cubren la deuda total."""
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("200.00")
    sales_record.save()
    
    vat_withholding.withheld_amount = Decimal("20.00")
    vat_withholding.save()
    
    ar = account_receivable_factory(sales_record=sales_record)
    
    payment = customer_payment_factory(total_amount=Decimal("180.00"))
    payment_imputation_factory(
        payment=payment,
        account_receivable=ar,
        imputed_amount=Decimal("180.00")
    )

    # Act
    balance = ar.net_receivable_balance

    # Assert
    assert balance == Decimal("0.00")


@pytest.mark.django_db
def test_ID_EC_001_net_retention_no_records(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable]
) -> None:
    """Comportamiento de accumulated_net_retention sin registros de retención."""
    # Arrange
    ar = account_receivable_factory(sales_record=sales_record)

    # Act
    net_retention = ar.accumulated_net_retention

    # Assert
    assert net_retention == Decimal("0.00")


@pytest.mark.django_db
def test_ID_EC_002_net_balance_no_imputations_null_sum(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable]
) -> None:
    """Fallback automático a 0.00 cuando el ORM retorna None en la agregación."""
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("100.00")
    sales_record.save()
    ar = account_receivable_factory(sales_record=sales_record)

    # Act
    balance = ar.net_receivable_balance

    # Assert
    assert balance == Decimal("100.00")


@pytest.mark.django_db
def test_ID_EC_003_over_imputation_forced_negative_balance(
    sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable],
    customer_payment_factory: Callable[..., CustomerPayment]
) -> None:
    """Evaluación del cálculo si las relaciones superan la deuda."""
    # Arrange
    sales_record.total_sales_inc_vat = Decimal("100.00")
    sales_record.save()
    ar = account_receivable_factory(sales_record=sales_record)
    
    payment = customer_payment_factory(total_amount=Decimal("150.00"))
    
    # Forzamos DB evadiendo full_clean para crear una sobre-imputación
    PaymentImputation.objects.create(
        fiscal_profile=ar.fiscal_profile,
        payment=payment,
        account_receivable=ar,
        fiscal_period=payment.fiscal_period,
        imputed_amount=Decimal("150.00")
    )

    # Act
    balance = ar.net_receivable_balance

    # Assert
    assert balance == Decimal("-50.00")




from decimal import Decimal
from typing import Callable

import pytest

from data_access.models.account_receivable import AccountReceivable
from data_access.models.sales_record import SalesRecord
from data_access.models.vat_withholding_sales import VatWithHolding


@pytest.mark.django_db
def test_net_receivable_balance_credit_note_without_withholding(
    sales_record: SalesRecord,
    credit_note_sales_record: SalesRecord,
    account_receivable_factory: Callable[..., AccountReceivable]
) -> None:
    """Verifica la disminución directa del Saldo Neto Cobrable por una Nota de Crédito 
    cuando la factura origen NO posee retenciones previas.
    
    Escenario Gherkin: Disminución directa del Saldo Neto Cobrable por Nota de Crédito 
    SIN retención previa en la factura origen.
    """
    # Arrange
    # Factura origen: total_sales_inc_vat = 116.00
    # Nota de crédito asociada: total_sales_inc_vat = 11.60
    ar = account_receivable_factory(sales_record=sales_record)

    # Act
    net_retention = ar.accumulated_net_retention
    balance = ar.net_receivable_balance

    # Assert
    # 1. No existen retenciones aplicadas
    assert net_retention == Decimal("0.00")
    # 2. Saldo Neto = (116.00 total factura - 11.60 monto NC) = 104.40
    assert balance == Decimal("104.40")


@pytest.mark.django_db
def test_net_receivable_balance_credit_note_with_adjustment_withholding(
    sales_record: SalesRecord,
    credit_note_sales_record: SalesRecord,
    vat_withholding: VatWithHolding,
    account_receivable_factory: Callable[..., AccountReceivable]
) -> None:
    """Verifica el cálculo del Saldo Neto Cobrable descontando el monto de la Nota de Crédito
    y la Retención Neta Acumulada (Retención Inicial - Retención de Ajuste NC).
    
    Escenario Gherkin: Ajuste del Saldo Neto Cobrable por Nota de Crédito CON retención 
    de ajuste (con retención previa).
    """
    # Arrange
    # 1. Factura origen tiene retención inicial en vat_withholding (12.00)
    # 2. Registrar la retención de ajuste para la Nota de Crédito (1.20)
    VatWithHolding.objects.create(
        fiscal_profile=vat_withholding.fiscal_profile,
        voucher_number="20260100000002",
        issue_date=vat_withholding.issue_date,
        fiscal_period=vat_withholding.fiscal_period,
        client_name=vat_withholding.client_name,
        client_rif=vat_withholding.client_rif,
        document_number=credit_note_sales_record.document_number,
        control_number=credit_note_sales_record.control_number,
        total_amount=Decimal("11.60"),
        tax_base=Decimal("10.00"),
        tax_caused=Decimal("1.60"),
        withheld_amount=Decimal("1.20"),
        client=vat_withholding.client,
        document=credit_note_sales_record
    )

    ar = account_receivable_factory(sales_record=sales_record)

    # Act
    net_retention = ar.accumulated_net_retention
    balance = ar.net_receivable_balance

    # Assert
    # 1. Retención Neta Acumulada = 12.00 (Factura) - 1.20 (NC) = 10.80
    assert net_retention == Decimal("10.80")
    
    # 2. Saldo Neto = (116.00 base - 11.60 NC) - 10.80 retención neta = 93.60
    assert balance == Decimal("93.60")