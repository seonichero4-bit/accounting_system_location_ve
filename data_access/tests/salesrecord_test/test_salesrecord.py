"""Suite de pruebas unitarias para validaciones y restricciones del modelo SalesRecord.

Este módulo implementa el plan de pruebas para verificar el comportamiento
de las restricciones a nivel de base de datos (Meta) y las validaciones 
de lógica de negocio en la capa de modelo (clean y save), cumpliendo con
las especificaciones tributarias y las convenciones de Django.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from data_access.models.customer import Customer
from data_access.models.sales_record import SalesRecord


@pytest.mark.django_db
class TestSalesRecordHappyPaths:
    """Conjunto de pruebas para los flujos principales (Happy Paths)."""

    def test_ID_HP_001_registro_exitoso_venta_interna_estandar(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Valida el guardado de un registro de venta interna con alícuota 16%."""
        # Arrange
        # base_sales_record ya viene configurado como venta interna al 16%

        # Act
        base_sales_record.full_clean()
        base_sales_record.save()

        # Assert
        assert base_sales_record.pk is not None
        assert base_sales_record.sale_type == "INTERNAL"

    def test_ID_HP_002_registro_exitoso_operacion_exportacion(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Valida el registro de venta de exportación respetando el valor FOB."""
        # Arrange
        base_sales_record.sale_type = "EXPORT"
        base_sales_record.fob_export_value = Decimal("500.00")
        base_sales_record.total_sales_inc_vat = Decimal("500.00")
        base_sales_record.general_tax_base_16 = Decimal("0.00")
        base_sales_record.general_tax_debit_16 = Decimal("0.00")

        # Act
        base_sales_record.full_clean()
        base_sales_record.save()

        # Assert
        assert base_sales_record.pk is not None
        assert base_sales_record.fob_export_value == Decimal("500.00")

    def test_ID_HP_003_registro_exitoso_nota_credito_vinculada(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Valida la creación de una nota de crédito vinculada a una factura previa."""
        # Arrange
        base_sales_record.save()
        credit_note = SalesRecord(
            fiscal_profile=base_sales_record.fiscal_profile,
            client=base_sales_record.client,
            document_type="CREDIT_NOTE",
            sale_type="INTERNAL",
            transaction_type="04_ADJUSTMENT",
            record_status="PRELIMINARY",
            document_date=timezone.now().date(),
            control_number="00-000002",
            invoice_number="00000101",
            total_sales_inc_vat=Decimal("58.00"),
            general_tax_base_16=Decimal("50.00"),
            general_tax_debit_16=Decimal("8.00"),
            affected_invoice=base_sales_record
        )

        # Act
        credit_note.full_clean()
        credit_note.save()

        # Assert
        assert credit_note.pk is not None
        assert credit_note.affected_invoice == base_sales_record

    def test_ID_HP_004_registro_exitoso_transaccion_anulada(
        self, base_sales_record: SalesRecord, annulled_customer: Customer
    ) -> None:
        """Valida la creación de un registro de anulación con montos en cero."""
        # Arrange
        base_sales_record.transaction_type = "03_ANNULMENT"
        base_sales_record.client = annulled_customer
        base_sales_record.total_sales_inc_vat = Decimal("0.00")
        base_sales_record.general_tax_base_16 = Decimal("0.00")
        base_sales_record.general_tax_debit_16 = Decimal("0.00")

        # Act
        base_sales_record.full_clean()
        base_sales_record.save()

        # Assert
        assert base_sales_record.pk is not None
        assert base_sales_record.record_status == "ANNULLED"  # Set by save/clean logic

    def test_ID_HP_005_modificacion_permitida_registro_preliminary(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Valida la actualización de datos sobre un registro en estado PRELIMINARY."""
        # Arrange
        base_sales_record.save()
        nueva_fecha = base_sales_record.document_date - timedelta(days=1)

        # Act
        base_sales_record.document_date = nueva_fecha
        base_sales_record.full_clean()
        base_sales_record.save()

        # Assert
        assert base_sales_record.document_date == nueva_fecha

    def test_ID_HP_006_registro_exitoso_impresora_fiscal(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Valida la secuencia de comprobantes de máquina fiscal."""
        # Arrange
        base_sales_record.fiscal_printer_number = "Z1F1234567"
        base_sales_record.z_report_number = "0100"
        base_sales_record.invoice_number = "000100"
        base_sales_record.last_receipt_number = "000105"

        # Act
        base_sales_record.full_clean()
        base_sales_record.save()

        # Assert
        assert base_sales_record.pk is not None

    def test_ID_HP_007_calculo_exacto_igtf_margen_tolerancia(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Verifica la validación del IGTF respetando tolerancia de redondeo (0.01)."""
        # Arrange
        base_sales_record.igtf_tax_base = Decimal("10.33")
        base_sales_record.igtf_tax_amount = Decimal("0.31")  # (10.33 * 0.03 = 0.3099 -> 0.31)

        # Act
        base_sales_record.full_clean()
        base_sales_record.save()

        # Assert
        assert base_sales_record.igtf_tax_amount == Decimal("0.31")

    def test_ID_HP_008_sanitizacion_automatica_numeros(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Valida la limpieza y formato del número de control y factura."""
        # Arrange
        base_sales_record.control_number = " 00-12345 "
        base_sales_record.invoice_number = " 456 "

        # Act
        base_sales_record.clean()

        # Assert
        assert base_sales_record.control_number == "00-12345"
        assert base_sales_record.invoice_number == "456"


@pytest.mark.django_db
class TestSalesRecordEdgeCases:
    """Conjunto de pruebas para casos de borde, violaciones y excepciones."""

    def test_ID_EC_001_violacion_unicidad_documento_emitido(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Intento de insertar un documento duplicado para el mismo perfil fiscal."""
        # Arrange
        base_sales_record.save()
        duplicado = SalesRecord(
            fiscal_profile=base_sales_record.fiscal_profile,
            client=base_sales_record.client,
            document_type=base_sales_record.document_type,
            control_number=base_sales_record.control_number,
            document_date=base_sales_record.document_date
        )

        # Act & Assert
        with pytest.raises((ValidationError, IntegrityError)):
            duplicado.full_clean()
            duplicado.save()

    def test_ID_EC_002_violacion_unicidad_reporte_z(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Intento de registrar dos veces el mismo Reporte Z."""
        # Arrange
        base_sales_record.fiscal_printer_number = "Z1F1234567"
        base_sales_record.z_report_number = "0100"
        base_sales_record.save()

        duplicado = SalesRecord(
            fiscal_profile=base_sales_record.fiscal_profile,
            client=base_sales_record.client,
            fiscal_printer_number="Z1F1234567",
            z_report_number="0100",
            document_date=base_sales_record.document_date
        )

        # Act & Assert
        with pytest.raises((ValidationError, IntegrityError)):
            duplicado.full_clean()
            duplicado.save()

    def test_ID_EC_003_montos_financieros_negativos(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Invalida montos negativos en campos financieros."""
        # Arrange
        base_sales_record.total_sales_inc_vat = Decimal("-50.00")

        # Act & Assert
        with pytest.raises((ValidationError, IntegrityError)):
            base_sales_record.full_clean()
            base_sales_record.save()

    def test_ID_EC_004_secuencia_comprobantes_invalida(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Invalida secuencia donde último recibo es menor al primero."""
        # Arrange
        base_sales_record.invoice_number = "000200"
        base_sales_record.last_receipt_number = "000199"

        # Act & Assert
        with pytest.raises((ValidationError, IntegrityError)):
            base_sales_record.full_clean()
            base_sales_record.save()

    def test_ID_EC_005_suma_montos_mayor_cero_anulacion(
        self, base_sales_record: SalesRecord, annulled_customer: Customer
    ) -> None:
        """Falla al crear transacción de anulación con montos > 0.00."""
        # Arrange
        base_sales_record.transaction_type = "03_ANNULMENT"
        base_sales_record.client = annulled_customer
        base_sales_record.total_sales_inc_vat = Decimal("100.00")

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()
        
        assert "transaction_type" in exc.value.error_dict

    def test_ID_EC_006_inconsistencia_ecuacion_contable(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Discrepancia entre el total facturado y la suma de bases imponibles/exenciones."""
        # Arrange
        base_sales_record.total_sales_inc_vat = Decimal("170.00")  # Real is 116.00

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()

        assert "total_sales_inc_vat" in exc.value.error_dict

    def test_ID_EC_007_desviacion_debito_fiscal_tolerancia(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Falla por desviación del 16% fuera del margen de tolerancia."""
        # Arrange
        base_sales_record.general_tax_debit_16 = Decimal("16.05")

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()

        assert "general_tax_debit_16" in exc.value.error_dict

    def test_ID_EC_008_debito_fiscal_presente_base_cero(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Invalida la presencia de débito cuando su base imponible es cero."""
        # Arrange
        base_sales_record.reduced_tax_base_8 = Decimal("0.00")
        base_sales_record.reduced_tax_debit_8 = Decimal("0.64")

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()
            
        assert "reduced_tax_debit_8" in exc.value.error_dict

    def test_ID_EC_009_omision_documento_afectado_nota_credito(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Exige asignar documento afectado a Notas de Crédito."""
        # Arrange
        base_sales_record.document_type = "CREDIT_NOTE"
        base_sales_record.affected_invoice = None

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()
            
        assert "affected_invoice" in exc.value.error_dict

    def test_ID_EC_010_asignacion_indebida_afectada_factura(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Prohíbe asignar documento afectado a una Factura regular."""
        # Arrange
        base_sales_record.document_type = "INVOICE"
        # Dummy assignation to test the validation (pointing to itself just in memory)
        base_sales_record.affected_invoice = base_sales_record 

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()
            
        assert "affected_invoice" in exc.value.error_dict

    def test_ID_EC_011_ausencia_datos_impresora_fiscal(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Exige N° Máquina y Z cuando se proporcionan datos de comprobante."""
        # Arrange
        base_sales_record.last_receipt_number = "000500"
        base_sales_record.fiscal_printer_number = ""

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()
            
        # Podría registrarse en un campo o en ambos
        errors = str(exc.value)
        assert "fiscal_printer_number" in errors or "z_report_number" in errors

    def test_ID_EC_012_cliente_no_valido_estado_anulado(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Prohíbe anulación si el cliente no es 'ANULADO'."""
        # Arrange
        base_sales_record.transaction_type = "03_ANNULMENT"
        # Client already set to standard_customer

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()
            
        assert "transaction_type" in exc.value.error_dict

    def test_ID_EC_013_desviacion_calculo_igtf(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Falla por desviación matemática entre base y monto IGTF."""
        # Arrange
        base_sales_record.igtf_tax_base = Decimal("100.00")
        base_sales_record.igtf_tax_amount = Decimal("4.00")

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()
            
        assert "igtf_tax_amount" in exc.value.error_dict

    def test_ID_EC_014_infraccion_fecha_futura(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Rechaza documentos con fechas futuras."""
        # Arrange
        base_sales_record.document_date = timezone.now().date() + timedelta(days=1)

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()
            
        assert "document_date" in exc.value.error_dict

    def test_ID_EC_015_incoherencia_export_ventas_internas(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Rechaza Venta Exportación con montos internos."""
        # Arrange
        base_sales_record.sale_type = "EXPORT"
        base_sales_record.fob_export_value = Decimal("100.00")
        base_sales_record.exempt_internal_sales = Decimal("10.00")

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()

    def test_ID_EC_016_incoherencia_internal_valor_fob(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Rechaza Venta Interna con montos de FOB de exportación."""
        # Arrange
        base_sales_record.sale_type = "INTERNAL"
        base_sales_record.fob_export_value = Decimal("50.00")

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()
            
        assert "fob_export_value" in exc.value.error_dict

    def test_ID_EC_017_violacion_inmutabilidad_save_processed(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Impide mutaciones a registros con estatus PROCESSED en método save()."""
        # Arrange
        base_sales_record.save()
        
        # Simulamos que un proceso lo marcó como procesado
        SalesRecord.objects.filter(pk=base_sales_record.pk).update(record_status="PROCESSED")
        base_sales_record.refresh_from_db()

        # Act & Assert
        base_sales_record.document_date = timezone.now().date()
        with pytest.raises(ValidationError) as exc:
            base_sales_record.save()
            
        assert "__all__" in exc.value.error_dict

    def test_ID_EC_018_violacion_inmutabilidad_save_annulled_processed(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Impide mutaciones a registros con estatus ANNULLED_PROCESSED en método save()."""
        # Arrange
        base_sales_record.save()
        
        # Simulamos que un proceso lo marcó como anulado y procesado
        SalesRecord.objects.filter(pk=base_sales_record.pk).update(record_status="ANNULLED_PROCESSED")
        base_sales_record.refresh_from_db()

        # Act & Assert
        base_sales_record.total_sales_inc_vat = Decimal("200.00")
        with pytest.raises(ValidationError) as exc:
            base_sales_record.save()
            
        assert "__all__" in exc.value.error_dict

    def test_ID_EC_019_formato_numero_control_invalido(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Invalida un número de control que no cumple el formato esperado."""
        # Arrange
        base_sales_record.control_number = "INVALID_FORMAT_123"

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()

    def test_ID_EC_020_acumulacion_masiva_errores_clean(
        self, base_sales_record: SalesRecord
    ) -> None:
        """Garantiza la compilación de múltiples errores simultáneos en error_dict."""
        # Arrange
        base_sales_record.total_sales_inc_vat = Decimal("999.00") # Falla ecuación
        base_sales_record.document_date = timezone.now().date() + timedelta(days=5) # Falla fecha futura
        base_sales_record.document_type = "CREDIT_NOTE"
        base_sales_record.affected_invoice = None # Falla omisión docto afectado

        # Act & Assert
        with pytest.raises(ValidationError) as exc:
            base_sales_record.full_clean()
            
        errors = exc.value.error_dict
        assert "total_sales_inc_vat" in errors
        assert "document_date" in errors
        assert "affected_invoice" in errors