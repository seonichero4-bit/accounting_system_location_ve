"""Suite de pruebas unitarias para el modelo VatWithHolding.

Verifica las restricciones de base de datos (class Meta) y las validaciones
de reglas de negocio (clean) definidas en la especificación técnica.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from data_access.models.sales_record import SalesRecord
from data_access.models.vat_withholding_sales import VatWithHolding


@pytest.mark.django_db
def test_ID_HP_001_create_valid_voucher_75_percent_retention(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_HP_001] Verifica el registro exitoso con retención del 75%."""
    # Arrange
    client.force_login(admin_user)
    valid_data = build_valid_voucher_data(sales_record)
    voucher = VatWithHolding(**valid_data)

    # Act
    voucher.full_clean()
    voucher.save()

    # Assert
    assert voucher.id is not None
    assert voucher.withheld_amount == Decimal("12.00")
    assert voucher.voucher_number == "20260100000001"


@pytest.mark.django_db
def test_ID_HP_002_create_valid_voucher_100_percent_retention(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_HP_002] Verifica el comportamiento al retener el 100% del débito fiscal."""
    # Arrange
    client.force_login(admin_user)
    valid_data = build_valid_voucher_data(sales_record)
    valid_data["withheld_amount"] = valid_data["tax_caused"]
    voucher = VatWithHolding(**valid_data)

    # Act
    voucher.full_clean()
    voucher.save()

    # Assert
    assert voucher.id is not None
    assert voucher.withheld_amount == Decimal("16.00")


@pytest.mark.django_db
def test_ID_EC_001_duplicate_voucher_raises_integrity_error(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_EC_001] Verifica la prevención de duplicidad por (voucher, cliente, perfil)."""
    # Arrange
    client.force_login(admin_user)
    valid_data = build_valid_voucher_data(sales_record)
    VatWithHolding.objects.create(**valid_data)

    # Se clona el registro origen para evitar colisión de la relación 'OneToOne' primero
    sales_record.pk = None
    sales_record.document_number = "00000002"
    sales_record.control_number = "00-00000002"
    sales_record.save()

    duplicate_data = build_valid_voucher_data(sales_record)
    duplicate_voucher = VatWithHolding(**duplicate_data)

    # Act & Assert
    with pytest.raises(IntegrityError):
        duplicate_voucher.save()


@pytest.mark.django_db
def test_ID_EC_002_voucher_number_short_length_raises_validation_error(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_EC_002] Verifica el validador Regex exigiendo 14 dígitos exactos (inferior)."""
    # Arrange
    client.force_login(admin_user)
    valid_data = build_valid_voucher_data(sales_record)
    valid_data["voucher_number"] = "2026010000000 "  # 13 dígitos
    voucher = VatWithHolding(**valid_data)

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        voucher.full_clean()
        
    assert "voucher_number" in exc_info.value.message_dict


@pytest.mark.django_db
def test_ID_EC_003_voucher_number_exceeds_length_raises_validation_error(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_EC_003] Verifica el validador Regex exigiendo 14 dígitos exactos (superior)."""
    # Arrange
    client.force_login(admin_user)
    valid_data = build_valid_voucher_data(sales_record)
    valid_data["voucher_number"] = "202601000000001"  # 15 dígitos
    voucher = VatWithHolding(**valid_data)

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        voucher.full_clean()
        
    assert "voucher_number" in exc_info.value.message_dict


@pytest.mark.django_db
def test_ID_EC_004_voucher_number_alphanumeric_raises_validation_error(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_EC_004] Verifica el rechazo de caracteres no numéricos en el secuencial."""
    # Arrange
    client.force_login(admin_user)
    valid_data = build_valid_voucher_data(sales_record)
    valid_data["voucher_number"] = "202601ABC00001"
    voucher = VatWithHolding(**valid_data)

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        voucher.full_clean()
        
    assert "voucher_number" in exc_info.value.message_dict


@pytest.mark.django_db
def test_ID_EC_005_negative_withheld_amount_raises_validation_error(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_EC_005] Verifica la restricción estricta y de formulario para montos negativos."""
    # Arrange
    client.force_login(admin_user)
    valid_data = build_valid_voucher_data(sales_record)
    valid_data["withheld_amount"] = Decimal("-10.50")
    voucher = VatWithHolding(**valid_data)

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        voucher.full_clean()
        
    assert "withheld_amount" in exc_info.value.message_dict


@pytest.mark.django_db
def test_ID_EC_006_annulled_source_document_raises_validation_error(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_EC_006] Verifica el bloqueo al intentar retener facturas anuladas."""
    # Arrange
    client.force_login(admin_user)
    sales_record.record_status = SalesRecord.RecordStatus.ANNULLED
    sales_record.save()
    
    valid_data = build_valid_voucher_data(sales_record)
    voucher = VatWithHolding(**valid_data)

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        voucher.full_clean()
        
    assert "__all__" in exc_info.value.message_dict


@pytest.mark.django_db
def test_ID_EC_007_processed_source_document_raises_validation_error(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_EC_007] Verifica el bloqueo de creación sobre facturas ya procesadas."""
    # Arrange
    client.force_login(admin_user)
    sales_record.record_status = SalesRecord.RecordStatus.PROCESSED
    sales_record.save()
    
    valid_data = build_valid_voucher_data(sales_record)
    voucher = VatWithHolding(**valid_data)

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        voucher.full_clean()
        
    assert "__all__" in exc_info.value.message_dict


@pytest.mark.django_db
def test_ID_EC_008_future_issue_date_raises_validation_error(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_EC_008] Verifica la prohibición de emisiones con fechas futuras."""
    # Arrange
    client.force_login(admin_user)
    future_date = timezone.now().date() + timedelta(days=1)
    
    valid_data = build_valid_voucher_data(sales_record)
    valid_data["issue_date"] = future_date
    valid_data["voucher_number"] = f"{future_date.strftime('%Y%m')}00000001"
    
    voucher = VatWithHolding(**valid_data)

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        voucher.full_clean()
        
    assert "issue_date" in exc_info.value.message_dict


@pytest.mark.django_db
def test_ID_EC_009_issue_date_before_document_date_raises_validation_error(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_EC_009] Verifica precedencia cronológica asegurando emisión no anterior al documento."""
    # Arrange
    client.force_login(admin_user)
    valid_data = build_valid_voucher_data(sales_record)
    # Según fixture, el doc fue emitido el 2026-01-20
    valid_data["issue_date"] = date(2026, 1, 10) 
    valid_data["voucher_number"] = "20260100000001"
    
    voucher = VatWithHolding(**valid_data)

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        voucher.full_clean()
        
    assert "issue_date" in exc_info.value.message_dict


@pytest.mark.django_db
def test_ID_EC_010_sequential_chronological_inconsistency_raises_validation_error(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_EC_010] Evalúa correlación obligatoria entre número de comprobante y fecha."""
    # Arrange
    client.force_login(admin_user)
    valid_data = build_valid_voucher_data(sales_record)
    valid_data["issue_date"] = date(2026, 5, 10)
    valid_data["voucher_number"] = "20260400000001"  # Desajuste Abril / Mayo
    voucher = VatWithHolding(**valid_data)

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        voucher.full_clean()
        
    assert "voucher_number" in exc_info.value.message_dict


@pytest.mark.django_db
def test_ID_EC_011_retention_percentage_out_of_legal_norm_raises_validation_error(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_EC_011] Verifica que el importe retenido sea estrictamente 75% o 100%."""
    # Arrange
    client.force_login(admin_user)
    valid_data = build_valid_voucher_data(sales_record)
    tax_caused = valid_data["tax_caused"]
    valid_data["withheld_amount"] = (tax_caused * Decimal("0.50")).quantize(Decimal("0.01"))
    
    voucher = VatWithHolding(**valid_data)

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        voucher.full_clean()
        
    assert "withheld_amount" in exc_info.value.message_dict


@pytest.mark.django_db
def test_ID_EC_012_withheld_amount_exceeds_tax_caused_raises_validation_error(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_EC_012] Verifica que la retención no exceda el débito fiscal de la factura."""
    # Arrange
    client.force_login(admin_user)
    valid_data = build_valid_voucher_data(sales_record)
    valid_data["withheld_amount"] = valid_data["tax_caused"] + Decimal("1.00")
    voucher = VatWithHolding(**valid_data)

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        voucher.full_clean()
        
    assert "withheld_amount" in exc_info.value.message_dict


@pytest.mark.django_db
def test_ID_EC_013_missing_mandatory_fields_raises_validation_error(client, admin_user, sales_record, build_valid_voucher_data):
    """[ID_EC_013] Verifica falla por ausencia de campos obligatorios (Null/Empty)."""
    # Arrange
    client.force_login(admin_user)
    valid_data = build_valid_voucher_data(sales_record)
    valid_data["voucher_number"] = None
    voucher = VatWithHolding(**valid_data)

    # Act & Assert
    with pytest.raises(ValidationError):
        voucher.full_clean()