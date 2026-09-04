"""Suite de pruebas unitarias para el modelo SalesRecord.

Verifica las restricciones de base de datos (Meta) y las validaciones 
de lógica de negocio (clean y save) según la especificación técnica.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.utils import timezone

from data_access.models.customer import Customer
from data_access.models.sales_record import SalesRecord


@pytest.mark.django_db
def test_id_hp_001_registro_exitoso_venta_interna_estandar(
    group_a_invoice_record: SalesRecord
) -> None:
    """Valida el guardado de una venta interna con alícuota general (16%)."""
    # Arrange: Registro configurado mediante fixture (group_a_invoice_record)
    
    # Act: Limpieza y persistencia
    group_a_invoice_record.full_clean()
    group_a_invoice_record.save()
    
    # Assert: El registro se persistió correctamente
    assert group_a_invoice_record.pk is not None
    assert group_a_invoice_record.sale_type == "INTERNAL"


@pytest.mark.django_db
def test_id_hp_002_registro_exitoso_operacion_exportacion(
    export_sales_record: SalesRecord
) -> None:
    """Confirma el registro para venta de exportación respetando el valor FOB."""
    # Arrange: Registro de exportación configurado mediante fixture
    
    # Act: Limpieza y persistencia
    export_sales_record.full_clean()
    export_sales_record.save()
    
    # Assert: La persistencia fue exitosa
    assert export_sales_record.pk is not None
    assert export_sales_record.fob_export_value == Decimal("500.00")
    assert export_sales_record.general_tax_base_16 == Decimal("0.00")


@pytest.mark.django_db
def test_id_hp_003_registro_exitoso_nota_credito_vinculada(
    persisted_sales_record: SalesRecord
) -> None:
    """Crea una nota de crédito asociando obligatoriamente una factura previa."""
    # Arrange: Se utiliza una factura previamente persistida y se crea una ND
    credit_note = SalesRecord(
        fiscal_profile=persisted_sales_record.fiscal_profile,
        client=persisted_sales_record.client,
        document_type="CREDIT_NOTE",
        document_number="0003",
        control_number="00-000003",
        sale_type="INTERNAL",
        transaction_type="04_ADJUSTMENT",
        record_status="PRELIMINARY",
        document_date=timezone.now().date(),
        total_sales_inc_vat=Decimal("116.00"),
        general_tax_base_16=Decimal("100.00"),
        general_tax_debit_16=Decimal("16.00"),
        exempt_internal_sales=Decimal("0.00"),
        exonerated_internal_sales=Decimal("0.00"),
        non_subject_internal_sales=Decimal("0.00"),
        reduced_tax_base_8=Decimal("0.00"),
        reduced_tax_debit_8=Decimal("0.00"),
        additional_tax_base_31=Decimal("0.00"),
        additional_tax_debit_31=Decimal("0.00"),
        igtf_tax_base=Decimal("0.00"),
        igtf_tax_amount=Decimal("0.00"),
        fob_export_value=Decimal("0.00"),
        affected_invoice=persisted_sales_record
    )
    
    # Act
    credit_note.full_clean()
    credit_note.save()
    
    # Assert
    assert credit_note.pk is not None
    assert credit_note.affected_invoice == persisted_sales_record


@pytest.mark.django_db
def test_id_hp_004_registro_exitoso_transaccion_anulada(
    annulled_sales_record: SalesRecord
) -> None:
    """Verifica que un registro anulado cumpla las restricciones y se guarde."""
    # Arrange: Fixture con transacción "03_ANNULMENT" y cliente "ANULADO"
    
    # Act
    annulled_sales_record.full_clean()
    annulled_sales_record.save()
    
    # Assert
    assert annulled_sales_record.pk is not None
    assert annulled_sales_record.transaction_type == "03_ANNULMENT"
    assert annulled_sales_record.total_sales_inc_vat == Decimal("0.00")


@pytest.mark.django_db
def test_id_hp_005_modificacion_permitida_registro_preliminary(
    persisted_sales_record: SalesRecord
) -> None:
    """Actualiza datos sobre un registro existente en estado PRELIMINARY."""
    # Arrange
    new_date = timezone.now().date() - timedelta(days=1)
    
    # Act
    persisted_sales_record.document_date = new_date
    persisted_sales_record.full_clean()
    persisted_sales_record.save()
    
    # Assert
    persisted_sales_record.refresh_from_db()
    assert persisted_sales_record.document_date == new_date


@pytest.mark.django_db
def test_id_hp_006_registro_exitoso_impresora_fiscal(
    group_b_fiscal_printer_record: SalesRecord
) -> None:
    """Valida registro por máquina fiscal asegurando secuencia válida."""
    # Arrange: Registro del Grupo B (campos del Grupo A ausentes/None)
    
    # Act
    group_b_fiscal_printer_record.full_clean()
    group_b_fiscal_printer_record.save()
    
    # Assert
    assert group_b_fiscal_printer_record.pk is not None
    assert group_b_fiscal_printer_record.fiscal_printer_number == "Z1F1234567"


def test_id_hp_007_calculo_exacto_igtf_con_margen_tolerancia(
    group_a_invoice_record: SalesRecord
) -> None:
    """Verifica la alícuota del 3% sobre base IGTF con tolerancia de 0.01."""
    # Arrange
    group_a_invoice_record.igtf_tax_base = Decimal("10.33")
    # 10.33 * 0.03 = 0.3099 -> tolerancia acepta 0.31
    group_a_invoice_record.igtf_tax_amount = Decimal("0.31") 
    
    # Act
    group_a_invoice_record.clean()
    
    # Assert: No se levantó ValidationError
    assert group_a_invoice_record.igtf_tax_amount == Decimal("0.31")


def test_id_hp_008_sanitizacion_automatica_numero_control_factura(
    group_a_invoice_record: SalesRecord,
    group_b_fiscal_printer_record: SalesRecord
) -> None:
    """Verifica limpieza de espacios en campos identificadores en clean()."""
   # Arrange
    group_a_invoice_record.control_number = " 00-12345 "

    # Asignar número de factura con espacios para probar la sanitización
    group_b_fiscal_printer_record.invoice_number = " 456 "

    # IMPORTANTE: Se actualiza 'last_receipt_number' a un valor mayor o igual (ej. " 460 ").
    # Si se omite, mantendrá el valor por defecto de la fixture ("000105"). Al ejecutar clean(),
    # la validación numérica (460 >= 456) fallará si 105 < 456, generando un ValidationError.
    group_b_fiscal_printer_record.last_receipt_number = " 460 "
    
    # Act
    group_a_invoice_record.clean()
    group_b_fiscal_printer_record.clean()
    
    # Assert
    assert group_a_invoice_record.control_number == "00-12345"
    assert group_b_fiscal_printer_record.invoice_number == "456"


@pytest.mark.django_db
def test_id_hp_009_normalizacion_implicita_save_grupo_a(
    group_a_invoice_record: SalesRecord
) -> None:
    """Verifica que el save() asigne None a campos no pertenecientes al Grupo A."""
    
    # Act
    group_a_invoice_record.save()
    
    # Assert
    assert group_a_invoice_record.fiscal_printer_number is None
    assert group_a_invoice_record.z_report_number is None


@pytest.mark.django_db
def test_id_hp_010_normalizacion_implicita_save_grupo_b(
    group_b_fiscal_printer_record: SalesRecord
) -> None:
    """Verifica que el save() asigne None a campos no pertenecientes al Grupo B."""
   
    # Act
    group_b_fiscal_printer_record.save()
    
    # Assert
    assert group_b_fiscal_printer_record.document_type is None
    assert group_b_fiscal_printer_record.control_number is None


@pytest.mark.django_db
def test_id_ec_001_violacion_unicidad_documento_emitido(
    persisted_sales_record: SalesRecord
) -> None:
    """Intento de insertar un documento duplicado para un mismo perfil fiscal."""
    # Arrange
    duplicate_record = SalesRecord(
        fiscal_profile=persisted_sales_record.fiscal_profile,
        client=persisted_sales_record.client,
        document_type=persisted_sales_record.document_type,
        document_number=persisted_sales_record.document_number,
        control_number=persisted_sales_record.control_number,
        document_date=persisted_sales_record.document_date
    )
    
    # Act & Assert
    with pytest.raises(IntegrityError):
        duplicate_record.save()


@pytest.mark.django_db
def test_id_ec_002_violacion_unicidad_reporte_z(
    group_b_fiscal_printer_record: SalesRecord
) -> None:
    """Intento de registrar dos veces la misma operación de Reporte Z."""
    # Arrange
    group_b_fiscal_printer_record.save()
    duplicate_z = SalesRecord(
        fiscal_profile=group_b_fiscal_printer_record.fiscal_profile,
        client=group_b_fiscal_printer_record.client,
        invoice_number=group_b_fiscal_printer_record.invoice_number,
        last_receipt_number=group_b_fiscal_printer_record.last_receipt_number,
        fiscal_printer_number=group_b_fiscal_printer_record.fiscal_printer_number,
        z_report_number=group_b_fiscal_printer_record.z_report_number,
        document_date=group_b_fiscal_printer_record.document_date
    )
    
    # Act & Assert
    with pytest.raises(IntegrityError):
        duplicate_z.save()


def test_id_ec_003_montos_financieros_negativos(
    group_a_invoice_record: SalesRecord
) -> None:
    """Intento de ingresar valores negativos en totales o bases imponibles."""
    # Arrange
    group_a_invoice_record.total_sales_inc_vat = Decimal("-50.00")
    
    # Act & Assert
    with pytest.raises(ValidationError):
        group_a_invoice_record.full_clean()


@pytest.mark.django_db
def test_id_ec_004_secuencia_comprobantes_invalida(
    group_b_fiscal_printer_record: SalesRecord
) -> None:
    """Último comprobante del día menor al primer comprobante."""
    # Arrange
    group_b_fiscal_printer_record.invoice_number = "000200"
    group_b_fiscal_printer_record.last_receipt_number = "000199"
    
    # Act & Assert
    with pytest.raises((ValidationError, IntegrityError)):
        group_b_fiscal_printer_record.full_clean()
        group_b_fiscal_printer_record.save()


def test_id_ec_005_suma_montos_mayor_a_cero_anulacion(
    annulled_sales_record: SalesRecord
) -> None:
    """Anulación con importes mayores a cero."""
    # Arrange
    annulled_sales_record.total_sales_inc_vat = Decimal("100.00")
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        annulled_sales_record.clean()
    assert "transaction_type" in exc_info.value.error_dict


def test_id_ec_006_inconsistencia_ecuacion_contable_total(
    group_a_invoice_record: SalesRecord
) -> None:
    """Discrepancia entre el total y la suma de los desgloses."""
    # Arrange (Suma real = 116.00)
    group_a_invoice_record.total_sales_inc_vat = Decimal("170.00")
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        group_a_invoice_record.clean()
    assert "total_sales_inc_vat" in exc_info.value.error_dict


def test_id_ec_007_desviacion_precision_debito_fiscal_fuera_tolerancia(
    group_a_invoice_record: SalesRecord
) -> None:
    """Débito fiscal con diferencia superior a 0.01."""
    # Arrange
    group_a_invoice_record.general_tax_base_16 = Decimal("100.00")
    group_a_invoice_record.general_tax_debit_16 = Decimal("16.05")
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        group_a_invoice_record.clean()
    assert "general_tax_debit_16" in exc_info.value.error_dict


def test_id_ec_008_debito_fiscal_presente_con_base_cero(
    group_a_invoice_record: SalesRecord
) -> None:
    """Débito fiscal mayor a cero cuando base imponible es cero."""
    # Arrange
    group_a_invoice_record.reduced_tax_base_8 = Decimal("0.00")
    group_a_invoice_record.reduced_tax_debit_8 = Decimal("0.64")
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        group_a_invoice_record.clean()
    assert "reduced_tax_debit_8" in exc_info.value.error_dict


def test_id_ec_009_omision_documento_afectado_nota_credito(
    group_a_invoice_record: SalesRecord
) -> None:
    """Nota de Crédito sin especificar factura afectada."""
    # Arrange
    group_a_invoice_record.document_type = "CREDIT_NOTE"
    group_a_invoice_record.affected_invoice = None
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        group_a_invoice_record.clean()
    assert "affected_invoice" in exc_info.value.error_dict


def test_id_ec_010_asignacion_indebida_documento_afectado_factura(
    group_a_invoice_record: SalesRecord,
    persisted_sales_record: SalesRecord
) -> None:
    """Factura regular con referencia a una factura afectada."""
    # Arrange
    group_a_invoice_record.document_type = "INVOICE"
    group_a_invoice_record.affected_invoice = persisted_sales_record
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        group_a_invoice_record.clean()
    assert "affected_invoice" in exc_info.value.error_dict


def test_id_ec_011_presencia_campos_impresora_fiscal_grupo_a(
    group_a_invoice_record: SalesRecord
) -> None:
    """Grupo A documentado simultáneamente con campos de máquina fiscal."""
    # Arrange
    group_a_invoice_record.invoice_number = "000100"
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        group_a_invoice_record.clean()
    assert "invoice_number" in exc_info.value.error_dict


def test_id_ec_012_omision_campos_obligatorios_grupo_a(
    group_a_invoice_record: SalesRecord
) -> None:
    """Registro del Grupo A omitiendo document_number."""
    # Arrange
    group_a_invoice_record.document_number = ""
    
    # Act & Assert
    with pytest.raises(ValidationError):
        group_a_invoice_record.full_clean()


def test_id_ec_013_presencia_campos_documentacion_interna_grupo_b(
    group_b_fiscal_printer_record: SalesRecord
) -> None:
    """Grupo B incluyendo campos propios de documentación interna."""
    # Arrange
    group_b_fiscal_printer_record.document_type = "INVOICE"
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        group_b_fiscal_printer_record.clean()
    assert "document_type" in exc_info.value.error_dict


def test_id_ec_014_incompleitud_campos_requeridos_impresora_fiscal_grupo_b(
    group_b_fiscal_printer_record: SalesRecord
) -> None:
    """Omisión de z_report_number dentro del trinomio de máquina fiscal."""
    # Arrange
    group_b_fiscal_printer_record.z_report_number = None
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        group_b_fiscal_printer_record.clean()
    assert "z_report_number" in exc_info.value.error_dict


def test_id_ec_015_cliente_no_valido_estado_anulado(
    annulled_sales_record: SalesRecord,
    standard_customer: Customer
) -> None:
    """Transacción anulada registrada a nombre de un cliente regular."""
    # Arrange
    annulled_sales_record.client = standard_customer
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        annulled_sales_record.clean()
    assert "transaction_type" in exc_info.value.error_dict


def test_id_ec_016_desviacion_calculo_igtf_fuera_margen(
    group_a_invoice_record: SalesRecord
) -> None:
    """Incoherencia matemática entre igtf_tax_base e igtf_tax_amount."""
    # Arrange
    group_a_invoice_record.igtf_tax_base = Decimal("100.00")
    group_a_invoice_record.igtf_tax_amount = Decimal("4.00")  # Debería ser 3.00
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        group_a_invoice_record.clean()
    assert "igtf_tax_amount" in exc_info.value.error_dict


def test_id_ec_017_infraccion_fecha_futura_documento(
    group_a_invoice_record: SalesRecord
) -> None:
    """Intento de registrar documento con fecha posterior a la actual."""
    # Arrange
    group_a_invoice_record.document_date = timezone.now().date() + timedelta(days=1)
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        group_a_invoice_record.clean()
    assert "document_date" in exc_info.value.error_dict


def test_id_ec_018_incoherencia_exportacion_con_ventas_internas(
    export_sales_record: SalesRecord
) -> None:
    """Operación EXPORT con montos registrados en ventas internas."""
    # Arrange
    export_sales_record.exempt_internal_sales = Decimal("10.00")
    export_sales_record.total_sales_inc_vat = Decimal("510.00")
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        export_sales_record.clean()
    assert "sale_type" in exc_info.value.error_dict or "fob_export_value" in exc_info.value.error_dict


def test_id_ec_019_incoherencia_venta_interna_con_valor_fob(
    group_a_invoice_record: SalesRecord
) -> None:
    """Operación INTERNAL con valor FOB mayor a cero."""
    # Arrange
    group_a_invoice_record.fob_export_value = Decimal("50.00")
    group_a_invoice_record.total_sales_inc_vat = Decimal("166.00")
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        group_a_invoice_record.clean()
    assert "fob_export_value" in exc_info.value.error_dict


@pytest.mark.django_db
def test_id_ec_020_violacion_inmutabilidad_save_processed(
    persisted_sales_record: SalesRecord
) -> None:
    """Intento de modificación sobre registro en estado PROCESSED."""
    # Arrange
    SalesRecord.objects.filter(pk=persisted_sales_record.pk).update(record_status="PROCESSED")
    persisted_sales_record.refresh_from_db()
    
    # Act & Assert
    persisted_sales_record.document_number = "MODIFICADO"
    with pytest.raises(ValidationError) as exc_info:
        persisted_sales_record.save()
    assert "__all__" in exc_info.value.error_dict


@pytest.mark.django_db
def test_id_ec_021_violacion_inmutabilidad_save_annulled_processed(
    persisted_sales_record: SalesRecord
) -> None:
    """Intento de modificación sobre registro en estado ANNULLED_PROCESSED."""
    # Arrange
    SalesRecord.objects.filter(pk=persisted_sales_record.pk).update(record_status="ANNULLED_PROCESSED")
    persisted_sales_record.refresh_from_db()
    
    # Act & Assert
    persisted_sales_record.control_number = "MODIFICADO"
    with pytest.raises(ValidationError) as exc_info:
        persisted_sales_record.save()
    assert "__all__" in exc_info.value.error_dict


def test_id_ec_022_formato_numero_control_invalido(
    group_a_invoice_record: SalesRecord
) -> None:
    """Cadena que viola las expresiones regulares de control."""
    # Arrange
    group_a_invoice_record.control_number = "INVALID_FORMAT_123"
    
    # Act & Assert
    with pytest.raises(ValidationError):
        group_a_invoice_record.full_clean()


def test_id_ec_023_acumulacion_masiva_errores_clean(
    group_a_invoice_record: SalesRecord
) -> None:
    """Envío de un objeto con múltiples infracciones simultáneas."""
    # Arrange
    group_a_invoice_record.total_sales_inc_vat = Decimal("999.00")  # Error 1: Ecuación
    group_a_invoice_record.document_date = timezone.now().date() + timedelta(days=2)  # Error 2: Fecha futura
    group_a_invoice_record.document_type = "CREDIT_NOTE"  # Error 3: Sin nota afectada
    
    # Act
    with pytest.raises(ValidationError) as exc_info:
        group_a_invoice_record.clean()
        
    # Assert
    errors = exc_info.value.error_dict
    assert len(errors) >= 3
    assert "total_sales_inc_vat" in errors
    assert "document_date" in errors
    assert "affected_invoice" in errors