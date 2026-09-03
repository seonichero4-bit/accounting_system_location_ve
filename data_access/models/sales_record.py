"""Módulo que define el modelo de datos para los registros del libro de ventas.

Implementa las validaciones estrictas y la estructura requerida por la normativa
tributaria venezolana y la especificación de negocio (SENIAT, IGTF, etc.).
"""

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

# Se asume la existencia de la clase base abstracta y el modelo de cliente
from data_access.models.base import FiscalModuleAbstractModel
from data_access.models.customer import Customer


class SalesRecord(FiscalModuleAbstractModel):
    """Modelo central que representa una transacción de venta y sus impuestos.
    
    Hereda de FiscalModuleAbstractModel para garantizar el aislamiento de inquilinos
    (tenant isolation) mediante el perfil fiscal.
    """

    class DocumentType(models.TextChoices):
        """Opciones válidas para los tipos de documentos fiscales."""
        INVOICE = 'INVOICE', 'Factura'
        CREDIT_NOTE = 'CREDIT_NOTE', 'Nota de Crédito'
        DEBIT_NOTE = 'DEBIT_NOTE', 'Nota de Débito'

    class TransactionType(models.TextChoices):
        """Naturaleza operativa de la transacción en el libro."""
        REGISTER = '01_REGISTER', '01 Registro'
        COMPLEMENT = '02_COMPLEMENT', '02 Complemento'
        ANNULMENT = '03_ANNULMENT', '03 Anulación'
        ADJUSTMENT = '04_ADJUSTMENT', '04 Ajuste'

    class SaleType(models.TextChoices):
        """Clasificación de venta (Nacional o Internacional)."""
        INTERNAL = 'INTERNAL', 'Interna'
        EXPORT = 'EXPORT', 'Exportación'

    class RecordStatus(models.TextChoices):
        """Ciclo de vida y estado actual del registro."""
        PRELIMINARY = 'PRELIMINARY', 'Preliminar'
        ANNULLED = 'ANNULLED', 'Anulado'
        PROCESSED = 'PROCESSED', 'Procesado'
        ANNULLED_PROCESSED = 'ANNULLED_PROCESSED', 'Anulado Procesado'

    # Identificación
    fiscal_period = models.DateField(null=True, blank=True)
    document_date = models.DateField()
    invoice_number = models.CharField(max_length=64, blank=True)
    last_receipt_number = models.CharField(max_length=64, blank=True)
    document_number = models.CharField(max_length=64, blank=True)
    
    control_number = models.CharField(
        max_length=64,
        validators=[
            RegexValidator(
                regex=r'^\d{2}-\d+$',
                message="Formato inválido de N° de Control."
            )
        ]
    )
    
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    sale_type = models.CharField(max_length=20, choices=SaleType.choices)
    fiscal_printer_number = models.CharField(max_length=64, blank=True)
    z_report_number = models.CharField(max_length=64, blank=True)
    
    record_status = models.CharField(
        max_length=20,
        choices=RecordStatus.choices,
        default=RecordStatus.PRELIMINARY
    )

    # Relaciones
    affected_invoice = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    client = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT
    )

    # Montos Consolidados y Exenciones
    total_sales_inc_vat = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    exempt_internal_sales = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    exonerated_internal_sales = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    non_subject_internal_sales = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Desglose de Impuestos (Ventas Gravadas por Alícuota)
    general_tax_base_16 = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    general_tax_debit_16 = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    reduced_tax_base_8 = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    reduced_tax_debit_8 = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    additional_tax_base_31 = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    additional_tax_debit_31 = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # IGTF (Agentes de percepción - Contribuyentes Especiales)
    igtf_tax_base = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    igtf_tax_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Comercio Exterior (Operaciones de Comercio Exterior)
    fob_export_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    class Meta:
        """Restricciones a nivel de base de datos para la entidad."""
        constraints = [
            models.UniqueConstraint(
                fields=['fiscal_profile', 'control_number', 'document_type'],
                name='unique_issued_document',
                violation_error_message="Ya existe un documento registrado con este N° de Control y Tipo de Documento para el perfil fiscal actual."
            ),
           models.UniqueConstraint(
                fields=['fiscal_profile', 'fiscal_printer_number', 'z_report_number'],
                condition=~Q(fiscal_printer_number="") & ~Q(z_report_number=""),
                name='unique_z_report',
                violation_error_message="Este N° de Reporte Z ya fue registrado previamente para la máquina fiscal especificada."
            ),
            models.CheckConstraint(
                condition=Q(total_sales_inc_vat__gte=0) & Q(general_tax_base_16__gte=0),
                name='positive_amounts',
                violation_error_message="El monto total de la venta y las bases imponibles deben ser mayores o iguales a 0.00."
            ),
            models.CheckConstraint(
                condition=Q(last_receipt_number__gte=F('invoice_number')) | Q(last_receipt_number=""),
                name='valid_receipt_sequence',
                violation_error_message="El número del último comprobante del día no puede ser menor al número del primer comprobante."
            ),
            models.CheckConstraint(
                condition=~Q(transaction_type='03_ANNULMENT') | Q(total_sales_inc_vat=0),
                name='zero_amount_on_annulment',
                violation_error_message="Las transacciones registradas como anulación requieren que la suma global de sus montos sea 0.00."
            )
        ]

    def clean(self) -> None:
        """Aplica la lógica de negocio, limpieza de datos y validaciones fiscales."""
        super().clean()
        errors: dict[str, Any] = {}

        # 1. Sanitización de campos
        if self.control_number:
            self.control_number = self.control_number.strip()
        if self.invoice_number:
            self.invoice_number = self.invoice_number.strip()

        # 2. Ecuación Contable del Total
        expected_total = (
            self.exempt_internal_sales + self.exonerated_internal_sales +
            self.non_subject_internal_sales + self.fob_export_value +
            self.general_tax_base_16 + self.general_tax_debit_16 +
            self.reduced_tax_base_8 + self.reduced_tax_debit_8 +
            self.additional_tax_base_31 + self.additional_tax_debit_31
        )
        if abs(self.total_sales_inc_vat - expected_total) > Decimal('0.01'):
            errors['total_sales_inc_vat'] = "El total de ventas incluido IVA no coincide con la suma de las ventas exentas, exoneradas, no sujetas, valor FOB y bases imponibles con sus débitos fiscales."

        # 3. Validación de Débitos Fiscales por Alícuota
        self._validate_tax(
            self.general_tax_base_16, self.general_tax_debit_16, Decimal('0.16'),
            'general_tax_debit_16', "El débito fiscal (16%) no coincide con el 16% de la base imponible general indicada.", errors
        )
        self._validate_tax(
            self.reduced_tax_base_8, self.reduced_tax_debit_8, Decimal('0.08'),
            'reduced_tax_debit_8', "El débito fiscal (8%) no coincide con el 8% de la base imponible reducida indicada.", errors
        )
        self._validate_tax(
            self.additional_tax_base_31, self.additional_tax_debit_31, Decimal('0.31'),
            'additional_tax_debit_31', "El débito fiscal (31%) no coincide con el 31% de la base imponible adicional indicada.", errors
        )

        # 4. Documentos Afectados (Notas de Crédito / Débito)
        if self.document_type in [self.DocumentType.CREDIT_NOTE, self.DocumentType.DEBIT_NOTE]:
            if not self.affected_invoice:
                errors['affected_invoice'] = "Las Notas de Crédito y Débito requieren especificar el N° de factura afectada, N° de control afectado y su fecha original."
        elif self.document_type == self.DocumentType.INVOICE:
            if self.affected_invoice:
                errors['affected_invoice'] = "Las facturas regulares no deben incluir referencia a una factura afectada."

        # 5. Soporte de Máquinas Fiscales
        if any([self.fiscal_printer_number, self.z_report_number, self.last_receipt_number]):
            if not all([self.fiscal_printer_number, self.z_report_number, self.invoice_number, self.last_receipt_number]):
                msg = "Las operaciones por máquina fiscal requieren N° de máquina fiscal, N° de reporte Z, N° de primer comprobante y N° de último comprobante."
                if not self.fiscal_printer_number:
                    errors['fiscal_printer_number'] = msg
                if not self.z_report_number:
                    errors['z_report_number'] = msg

        # 6. Reglas de Anulación
        if self.transaction_type == self.TransactionType.ANNULMENT or self.record_status == self.RecordStatus.ANNULLED:
            if not getattr(self, 'client', None) or self.client.name != 'ANULADO':
                errors['transaction_type'] = "Para transacciones de anulación, el nombre o razón social debe ser 'ANULADO' y todos los montos deben ser iguales a 0.00."
            
            amounts_sum = (
                self.total_sales_inc_vat + self.exempt_internal_sales + self.exonerated_internal_sales +
                self.non_subject_internal_sales + self.fob_export_value +
                self.general_tax_base_16 + self.general_tax_debit_16 +
                self.reduced_tax_base_8 + self.reduced_tax_debit_8 +
                self.additional_tax_base_31 + self.additional_tax_debit_31 +
                self.igtf_tax_base + self.igtf_tax_amount
            )
            if amounts_sum > Decimal('0.00'):
                errors['transaction_type'] = "Para transacciones de anulación, el nombre o razón social debe ser 'ANULADO' y todos los montos deben ser iguales a 0.00."

        # 7. Cálculo de IGTF Percibido (3%)
        if self.igtf_tax_base > Decimal('0.00'):
            if abs(self.igtf_tax_amount - (self.igtf_tax_base * Decimal('0.03'))) > Decimal('0.01'):
                errors['igtf_tax_amount'] = "El monto de IGTF debe corresponder exactamente al 3% de la base imponible de IGTF declarada."
        elif self.igtf_tax_base == Decimal('0.00') and self.igtf_tax_amount > Decimal('0.00'):
             errors['igtf_tax_amount'] = "El monto de IGTF debe corresponder exactamente al 3% de la base imponible de IGTF declarada."

        # 8. Restricción de Fecha Futura
        if self.document_date and self.document_date > timezone.now().date():
            errors['document_date'] = "La fecha del documento no puede ser posterior a la fecha actual del sistema."

        # 9. Consistencia por Tipo de Venta
        if self.sale_type == self.SaleType.EXPORT:
            if self.fob_export_value <= Decimal('0.00') or self.exempt_internal_sales > Decimal('0.00'):
                errors['sale_type'] = "Para operaciones de exportación, el valor FOB debe ser mayor a 0.00 y los campos de ventas internas deben ser 0.00."
        elif self.sale_type == self.SaleType.INTERNAL:
            if self.fob_export_value > Decimal('0.00'):
                errors['fob_export_value'] = "Para operaciones de ventas internas, el valor FOB de exportación debe ser 0.00 o nulo."

        # Emitir conjunto consolidado de errores
        if errors:
            raise ValidationError(errors)

    def _validate_tax(self, base: Decimal, debit: Decimal, rate: Decimal, field: str, deviation_msg: str, errors: dict) -> None:
        """Valida que el débito corresponda a la base declarada dentro del margen de tolerancia."""
        if base > Decimal('0.00'):
            expected_debit = base * rate
            if abs(debit - expected_debit) > Decimal('0.01'):
                errors[field] = deviation_msg
        elif base == Decimal('0.00') and debit > Decimal('0.00'):
            errors[field] = "El débito fiscal debe ser exactamente 0.00 cuando la base imponible asociada sea igual a 0.00 o nula."

    def save(self, *args, **kwargs) -> None:
        """Sobrescribe el guardado para imponer inmutabilidad y procesar anulaciones."""
        if self.pk:
            old_instance = type(self).objects.get(pk=self.pk)
            if old_instance.record_status in [self.RecordStatus.PROCESSED, self.RecordStatus.ANNULLED_PROCESSED]:
                raise ValidationError({
                    '__all__': "No se puede modificar un registro del Libro de Ventas que ya se encuentra en estatus 'Procesado' o 'Anulado Procesado'."
                })

        if self.transaction_type == self.TransactionType.ANNULMENT:
            self.record_status = self.RecordStatus.ANNULLED
            
        super().save(*args, **kwargs)