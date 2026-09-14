
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client

from data_access.models.customer import Customer
from data_access.models.islr_withholding_sales import IslrWithHolding


# ==============================================================================
# 1. HAPPY PATHS (FLUJOS FELICES)
# ==============================================================================

@pytest.mark.django_db
def test_create_islr_withholding_valid_values_exact_calculations_ID_HP_001(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    voucher_number = "00000001"
    gross_amount = Decimal("1000.00")
    tax_base = Decimal("1000.00")
    retention_percentage = Decimal("3.00")
    subtracting = Decimal("10.00")
    total_withheld_amount = Decimal("20.00")
    net_amount_to_pay = Decimal("980.00")

    # Act
    instance = islr_withholding_factory(
        commit=True,
        validate=True,
        voucher_number=voucher_number,
        gross_amount=gross_amount,
        tax_base=tax_base,
        retention_percentage=retention_percentage,
        subtracting=subtracting,
        total_withheld_amount=total_withheld_amount,
        net_amount_to_pay=net_amount_to_pay
    )

    # Assert
    assert instance.pk is not None
    assert instance.voucher_number == voucher_number
    assert instance.total_withheld_amount == total_withheld_amount
    assert instance.net_amount_to_pay == net_amount_to_pay


@pytest.mark.django_db
def test_tax_base_less_than_gross_amount_valid_ID_HP_002(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    gross_amount = Decimal("5000.00")
    tax_base = Decimal("3000.00")
    retention_percentage = Decimal("5.00")
    subtracting = Decimal("0.00")
    total_withheld_amount = Decimal("150.00")
    net_amount_to_pay = Decimal("4850.00")

    # Act
    instance = islr_withholding_factory(
        commit=True,
        validate=True,
        gross_amount=gross_amount,
        tax_base=tax_base,
        retention_percentage=retention_percentage,
        subtracting=subtracting,
        total_withheld_amount=total_withheld_amount,
        net_amount_to_pay=net_amount_to_pay
    )

    # Assert
    assert instance.pk is not None
    assert instance.tax_base <= instance.gross_amount


@pytest.mark.django_db
def test_retention_percentage_lower_limit_1_percent_ID_HP_003(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    gross_amount = Decimal("1000.00")
    tax_base = Decimal("1000.00")
    retention_percentage = Decimal("1.00")
    subtracting = Decimal("0.00")
    total_withheld_amount = Decimal("10.00")
    net_amount_to_pay = Decimal("990.00")

    # Act
    instance = islr_withholding_factory(
        commit=False,
        validate=True,
        gross_amount=gross_amount,
        tax_base=tax_base,
        retention_percentage=retention_percentage,
        subtracting=subtracting,
        total_withheld_amount=total_withheld_amount,
        net_amount_to_pay=net_amount_to_pay
    )

    # Assert
    assert instance.retention_percentage == Decimal("1.00")


@pytest.mark.django_db
def test_retention_percentage_upper_limit_100_percent_ID_HP_004(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    gross_amount = Decimal("1000.00")
    tax_base = Decimal("500.00")
    retention_percentage = Decimal("100.00")
    subtracting = Decimal("0.00")
    total_withheld_amount = Decimal("500.00")
    net_amount_to_pay = Decimal("500.00")

    # Act
    instance = islr_withholding_factory(
        commit=False,
        validate=True,
        gross_amount=gross_amount,
        tax_base=tax_base,
        retention_percentage=retention_percentage,
        subtracting=subtracting,
        total_withheld_amount=total_withheld_amount,
        net_amount_to_pay=net_amount_to_pay
    )

    # Assert
    assert instance.retention_percentage == Decimal("100.00")


@pytest.mark.django_db
def test_islr_calculation_rounding_tolerance_ID_HP_005(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    gross_amount = Decimal("1000.00")
    tax_base = Decimal("1000.00")
    retention_percentage = Decimal("3.33")
    subtracting = Decimal("0.00")
    total_withheld_amount = Decimal("33.31")  # expected_amount es 33.30 (diferencia +0.01)
    net_amount_to_pay = Decimal("966.69")

    # Act
    instance = islr_withholding_factory(
        commit=False,
        validate=True,
        gross_amount=gross_amount,
        tax_base=tax_base,
        retention_percentage=retention_percentage,
        subtracting=subtracting,
        total_withheld_amount=total_withheld_amount,
        net_amount_to_pay=net_amount_to_pay
    )

    # Assert
    assert instance.total_withheld_amount == Decimal("33.31")


@pytest.mark.django_db
def test_reuse_voucher_number_different_client_or_profile_ID_HP_006(
    client: Client,
    islr_withholding_factory,
    standard_customer,
    second_customer,
    sales_record,
    second_sales_record
):
    # Arrange
    voucher_number = "00000100"

    # Act
    instance_a = islr_withholding_factory(
        commit=True,
        validate=True,
        voucher_number=voucher_number,
        client=standard_customer,
        document=sales_record
    )
    instance_b = islr_withholding_factory(
        commit=True,
        validate=True,
        voucher_number=voucher_number,
        client=second_customer,
        document=second_sales_record,
        client_name=second_customer.name,
        client_rif=second_customer.rif,
        document_number=second_sales_record.document_number,
        control_number=second_sales_record.control_number
    )

    # Assert
    assert instance_a.pk is not None
    assert instance_b.pk is not None
    assert instance_a.voucher_number == instance_b.voucher_number
    assert instance_a.client != instance_b.client
    assert instance_a.document != instance_b.document


# ==============================================================================
# 2. EDGE CASES (CASOS BORDE Y MANEJO DE ERRORES)
# ==============================================================================

@pytest.mark.django_db
def test_unique_voucher_per_profile_and_client_constraint_ID_EC_001(
    client: Client,
    islr_withholding_factory,
    standard_customer,
    fiscal_profile
):
    # Arrange
    voucher_number = "00000100"
    islr_withholding_factory(
        commit=True,
        validate=True,
        voucher_number=voucher_number,
        client=standard_customer,
        fiscal_profile=fiscal_profile
    )

    # Act & Assert
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            islr_withholding_factory(
                commit=True,
                validate=False,
                voucher_number=voucher_number,
                client=standard_customer,
                fiscal_profile=fiscal_profile
            )


@pytest.mark.django_db
def test_check_constraint_tax_base_lte_gross_amount_db_ID_EC_002(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    gross_amount = Decimal("1000.00")
    tax_base = Decimal("2000.00")

    # Act & Assert
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            islr_withholding_factory(
                commit=True,
                validate=False,
                gross_amount=gross_amount,
                tax_base=tax_base
            )


@pytest.mark.django_db
def test_monetary_fields_zero_value_rejected_ID_EC_003(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    instance = islr_withholding_factory(
        commit=False,
        validate=False,
        gross_amount=Decimal("0.00")
    )

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        instance.full_clean()

    errors = exc_info.value.message_dict
    assert "gross_amount" in errors
    assert any(
        "El monto ingresado no puede ser negativo. Debe ser un valor mayor o igual a 0.01." in msg
        for msg in errors["gross_amount"]
    )


@pytest.mark.django_db
def test_monetary_fields_negative_value_rejected_ID_EC_004(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    instance = islr_withholding_factory(
        commit=False,
        validate=False,
        gross_amount=Decimal("-500.00")
    )

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        instance.full_clean()

    errors = exc_info.value.message_dict
    assert "gross_amount" in errors
    assert any(
        "El monto ingresado no puede ser negativo. Debe ser un valor mayor o igual a 0.01." in msg
        for msg in errors["gross_amount"]
    )


@pytest.mark.django_db
def test_retention_percentage_below_min_1_percent_ID_EC_005(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    instance = islr_withholding_factory(
        commit=False,
        validate=False,
        retention_percentage=Decimal("0.00")
    )

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        instance.full_clean()

    errors = exc_info.value.message_dict
    assert "retention_percentage" in errors
    assert any(
        "El porcentaje de retención debe estar comprendido entre el 1.00% y el 100.00%." in msg
        for msg in errors["retention_percentage"]
    )


@pytest.mark.django_db
def test_retention_percentage_above_max_100_percent_ID_EC_006(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    instance = islr_withholding_factory(
        commit=False,
        validate=False,
        retention_percentage=Decimal("100.01")
    )

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        instance.full_clean()

    errors = exc_info.value.message_dict
    assert "retention_percentage" in errors
    assert any(
        "El porcentaje de retención debe estar comprendido entre" in msg
        for msg in errors["retention_percentage"]
    )


@pytest.mark.django_db
def test_clean_tax_base_exceeds_gross_amount_ID_EC_007(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    instance = islr_withholding_factory(
        commit=False,
        validate=False,
        gross_amount=Decimal("1000.00"),
        tax_base=Decimal("1500.00")
    )

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        instance.clean()

    errors = exc_info.value.message_dict
    assert "tax_base" in errors
    assert any(
        "La base imponible no puede exceder el monto bruto de la operación." in msg
        for msg in errors["tax_base"]
    )


@pytest.mark.django_db
def test_clean_islr_withheld_amount_discrepancy_exceeds_tolerance_ID_EC_008(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    instance = islr_withholding_factory(
        commit=False,
        validate=False,
        gross_amount=Decimal("1000.00"),
        tax_base=Decimal("1000.00"),
        retention_percentage=Decimal("3.00"),
        subtracting=Decimal("0.00"),
        total_withheld_amount=Decimal("30.02")
    )

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        instance.clean()

    errors = exc_info.value.message_dict
    assert "total_withheld_amount" in errors
    assert any(
        "El monto total retenido no coincide con el cálculo del ISLR según la base imponible, el porcentaje y el sustraendo aplicados." in msg
        for msg in errors["total_withheld_amount"]
    )


@pytest.mark.django_db
def test_clean_net_amount_to_pay_discrepancy_ID_EC_009(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    instance = islr_withholding_factory(
        commit=False,
        validate=False,
        gross_amount=Decimal("1000.00"),
        total_withheld_amount=Decimal("30.00"),
        net_amount_to_pay=Decimal("969.00")
    )

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        instance.clean()

    errors = exc_info.value.message_dict
    assert "net_amount_to_pay" in errors
    assert any(
        "El monto neto a pagar es incorrecto. Debe ser igual a la diferencia entre el monto bruto y el monto total retenido." in msg
        for msg in errors["net_amount_to_pay"]
    )


@pytest.mark.django_db
def test_clean_multiple_validation_errors_accumulation_ID_EC_010(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    instance = islr_withholding_factory(
        commit=False,
        validate=False,
        gross_amount=Decimal("1000.00"),
        tax_base=Decimal("1200.00"),
        retention_percentage=Decimal("3.00"),
        subtracting=Decimal("0.00"),
        total_withheld_amount=Decimal("50.00"),
        net_amount_to_pay=Decimal("800.00")
    )

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        instance.clean()

    errors = exc_info.value.message_dict
    assert "tax_base" in errors
    assert "total_withheld_amount" in errors
    assert "net_amount_to_pay" in errors
    assert any(
        "La base imponible no puede exceder el monto bruto de la operación." in msg
        for msg in errors["tax_base"]
    )
    assert any(
        "El monto total retenido no coincide con el cálculo del ISLR según la base imponible, el porcentaje y el sustraendo aplicados." in msg
        for msg in errors["total_withheld_amount"]
    )
    assert any(
        "El monto neto a pagar es incorrecto. Debe ser igual a la diferencia entre el monto bruto y el monto total retenido." in msg
        for msg in errors["net_amount_to_pay"]
    )


@pytest.mark.django_db
def test_clean_null_quantitative_attributes_handling_ID_EC_011(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    instance = islr_withholding_factory(
        commit=False,
        validate=False,
        tax_base=None,
        gross_amount=None
    )

    # Act & Assert
    try:
        instance.clean()
    except ValidationError:
        pass
    except TypeError as exc:
        pytest.fail(f"clean() lanzó TypeError inesperado con atributos nulos: {exc}")


@pytest.mark.django_db
def test_excessive_subtracting_resulting_in_invalid_withheld_amount_ID_EC_012(
    client: Client,
    islr_withholding_factory
):
    # Arrange
    instance = islr_withholding_factory(
        commit=False,
        validate=False,
        tax_base=Decimal("100.00"),
        retention_percentage=Decimal("1.00"),
        subtracting=Decimal("50.00"),
        total_withheld_amount=Decimal("-49.00")
    )

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        instance.full_clean()

    errors = exc_info.value.message_dict
    assert "total_withheld_amount" in errors
    assert any(
        "El monto ingresado no puede ser negativo. Debe ser un valor mayor o igual a 0.01." in msg
        for msg in errors["total_withheld_amount"]
    )