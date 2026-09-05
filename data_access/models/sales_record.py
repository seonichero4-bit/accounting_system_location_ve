"""Módulo de definición del modelo SalesRecord (Libro de Ventas).

Implementa la estructura de base de datos y la lógica de negocio para
el registro de operaciones de ventas, cumpliendo estrictamente con la
legislación fiscal venezolana y garantizando el aislamiento multi-tenant.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from data_access.models.base import FiscalModuleAbstractModel
from data_access.models.customer import Customer


class SalesRecord(FiscalModuleAbstractModel):
    """Modelo representativo de un registro en el Libro de Ventas fiscal."""

    class DocumentType(models.TextChoices):
        """Tipos de documentos fiscales internos."""
        INVOICE = 'INVOICE', 'Factura'
        CREDIT_NOTE = 'CREDIT_NOTE', 'Nota de Crédito'
        DEBIT_NOTE = 'DEBIT_NOTE', 'Nota de Débito'

    class TransactionType(models.TextChoices):
        """Clasificación de transacciones fiscales."""
        REGISTER = '01_REGISTER', '01 Registro'
        COMPLEMENT = '02_COMPLEMENT', '02 Complemento'
        ANNULMENT = '03_ANNULMENT', '03 Anulación'
        ADJUSTMENT = '04_ADJUSTMENT', '04 Ajuste'

    class SaleType(models.TextChoices):
        """Tipos de operaciones de venta."""
        INTERNAL = 'INTERNAL', 'Interna'
        EXPORT = 'EXPORT', 'Exportación'

    class RecordStatus(models.TextChoices):
        """Estados del ciclo de vida del registro."""
        PRELIMINARY = 'PRELIMINARY', 'Preliminar'
        ANNULLED = 'ANNULLED', 'Anulado'
        PROCESSED = 'PROCESSED', 'Procesado'
        ANNULLED_PROCESSED = 'ANNULLED_PROCESSED', 'Anulado_Procesado'

    # Identificación
    fiscal_period = models.DateField(null=True, blank=True)
    document_date = models.DateField()
    invoice_number = models.CharField(max_length=20, null=True, blank=True)
    last_receipt_number = models.CharField(max_length=20, null=True, blank=True)
    document_number = models.CharField(max_length=20, null=True, blank=True)
    control_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\s*\d{2}-\d+\s*$',
                message="Formato inválido"
            )
        ]
    )
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        null=True,
        blank=True
    )
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    sale_type = models.CharField(max_length=20, choices=SaleType.choices)
    fiscal_printer_number = models.CharField(max_length=50, null=True, blank=True)
    z_report_number = models.CharField(max_length=50, null=True, blank=True)
    record_status = models.CharField(
        max_length=20,
        choices=RecordStatus.choices,
        default=RecordStatus.PRELIMINARY,
        blank=True   ### ACTUALIZAR EN LA SPEC
    )

    # Relaciones
    affected_invoice = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    client = models.ForeignKey(Customer, on_delete=models.PROTECT)

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

    # Desglose de Impuestos
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

    # IGTF
    igtf_tax_base = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    igtf_tax_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Comercio Exterior
    fob_export_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['fiscal_profile', 'control_number', 'document_type'],
                name='unique_issued_document'
            ),
            models.UniqueConstraint(
                fields=['fiscal_profile', 'fiscal_printer_number', 'z_report_number', 'invoice_number', 'last_receipt_number'],
                name='unique_z_report'
            ),
            models.CheckConstraint(
                condition=(
                    Q(total_sales_inc_vat__gte=0) &
                    Q(general_tax_base_16__gte=0) &
                    Q(reduced_tax_base_8__gte=0) &
                    Q(additional_tax_base_31__gte=0) &
                    Q(igtf_tax_base__gte=0) &
                    Q(exempt_internal_sales__gte=0) &
                    Q(exonerated_internal_sales__gte=0) &
                    Q(non_subject_internal_sales__gte=0) &
                    Q(fob_export_value__gte=0)
                ),
                name='positive_amounts'
            ),
            models.CheckConstraint(
                condition=Q(last_receipt_number__gte=F('invoice_number')) | Q(last_receipt_number__isnull=True) | Q(invoice_number__isnull=True),
                name='valid_receipt_sequence'
            ),
            models.CheckConstraint(
                condition=~Q(transaction_type='03_ANNULMENT') | Q(total_sales_inc_vat=0),
                name='zero_amount_on_annulment'
            ),
        ]

    def __str__(self) -> str:
        identifier = self.document_number or self.invoice_number or f"ID-{self.pk or 'nuevo'}"
        return f"SalesRecord({identifier})"

    def __repr__(self) -> str:
        return f"<SalesRecord id={self.pk} doc={self.document_number or self.invoice_number}>"

    def clean(self) -> None:
        """Aplica la lógica de validación de negocio y sanitaria del modelo."""
        errors = {}

        # Sanitización de campos identificadores
        if self.control_number:
            self.control_number = self.control_number.strip()
        if self.invoice_number:
            self.invoice_number = self.invoice_number.strip()
        if self.last_receipt_number:
            self.last_receipt_number = self.last_receipt_number.strip()

        # Condicionales de Activación (Grupos)
        is_group_a = bool(self.document_type)
        is_group_b = bool(self.invoice_number or self.fiscal_printer_number or self.z_report_number)

        # Validación Grupo A: Documentación Fiscal Interna
        if is_group_a:
            if any([self.invoice_number, self.last_receipt_number, self.fiscal_printer_number, self.z_report_number]):
                errors['invoice_number'] = (
                    "Los campos de impresora fiscal (N° de factura/comprobante, N° de último comprobante, "
                    "N° de máquina fiscal y N° de reporte Z) deben estar vacíos al registrar documentación fiscal interna."
                )

            if self.document_type == self.DocumentType.INVOICE and self.affected_invoice:
                errors['affected_invoice'] = "Las facturas de tipo 'INVOICE' no deben incluir referencia a una factura afectada."
            
            if self.document_type in [self.DocumentType.CREDIT_NOTE, self.DocumentType.DEBIT_NOTE] and not self.affected_invoice:
                errors['affected_invoice'] = (
                    "Las Notas de Crédito y Débito requieren especificar el N° de factura afectada, "
                    "N° de control afectado y su fecha original."
                )

            if not self.document_number:
                errors['document_number'] = "El número de documento es requerido y debe ser un valor válido."
            if not self.control_number:
                errors['control_number'] = "El número de control es requerido y debe ser un valor válido."

        # Validación Grupo B: Impresora Fiscal
        if is_group_b:
            if any([self.document_type, self.document_number, self.control_number, self.affected_invoice]):
                errors['document_type'] = (
                    "Los campos de documentación interna (tipo de documento, N° de documento, "
                    "N° de control y factura afectada) deben estar vacíos cuando se registra una operación de impresora fiscal."
                )
            
            if not all([self.invoice_number, self.fiscal_printer_number, self.z_report_number]):
                errors['z_report_number'] = (
                    "El registro de impresora fiscal requiere que el N° de factura/comprobante, "
                    "el N° de máquina fiscal y el N° de reporte Z estén presentes simultáneamente."
                )

            # Validar secuencia de comprobantes lógicamente si ambos están presentes
            if self.invoice_number and self.last_receipt_number:
                inv_num = int(self.invoice_number) if self.invoice_number.isdigit() else self.invoice_number
                last_num = int(self.last_receipt_number) if self.last_receipt_number.isdigit() else self.last_receipt_number
                
                if last_num < inv_num:
                    errors['last_receipt_number'] = (
                        "El número del último comprobante del día no puede ser menor al número del primer comprobante."
                    )

        # Ecuación Contable del Total
        expected_total = sum([
            self.exempt_internal_sales or Decimal('0.00'),
            self.exonerated_internal_sales or Decimal('0.00'),
            self.non_subject_internal_sales or Decimal('0.00'),
            self.fob_export_value or Decimal('0.00'),
            self.general_tax_base_16 or Decimal('0.00'),
            self.general_tax_debit_16 or Decimal('0.00'),
            self.reduced_tax_base_8 or Decimal('0.00'),
            self.reduced_tax_debit_8 or Decimal('0.00'),
            self.additional_tax_base_31 or Decimal('0.00'),
            self.additional_tax_debit_31 or Decimal('0.00'),
        ])
        
        if (self.total_sales_inc_vat or Decimal('0.00')) != expected_total:
            errors['total_sales_inc_vat'] = (
                "El total de ventas incluido IVA no coincide con la suma de las ventas exentas, "
                "exoneradas, no sujetas, valor FOB y bases imponibles con sus débitos fiscales."
            )

        # Cálculo de Débitos Fiscales (16%, 8%, 31%)
        def check_debit(base: Decimal, debit: Decimal, rate: str, field: str, name_rate: str) -> None:
            base_val = base or Decimal('0.00')
            debit_val = debit or Decimal('0.00')
            if base_val > Decimal('0.00'):
                if abs((base_val * Decimal(rate)) - debit_val) > Decimal('0.01'):
                    errors[field] = f"El débito fiscal ({name_rate}%) no coincide con el {name_rate}% de la base imponible {('general' if name_rate == '16' else 'reducida' if name_rate == '8' else 'adicional')} indicada."
            elif base_val == Decimal('0.00') and debit_val > Decimal('0.00'):
                errors[field] = "El débito fiscal debe ser exactamente 0.00 cuando la base imponible asociada sea igual a 0.00 o nula."

        check_debit(self.general_tax_base_16, self.general_tax_debit_16, '0.16', 'general_tax_debit_16', '16')
        check_debit(self.reduced_tax_base_8, self.reduced_tax_debit_8, '0.08', 'reduced_tax_debit_8', '8')
        check_debit(self.additional_tax_base_31, self.additional_tax_debit_31, '0.31', 'additional_tax_debit_31', '31')

        # Anulación de Documentos
        is_annulled = self.transaction_type == self.TransactionType.ANNULMENT or self.record_status == self.RecordStatus.ANNULLED
        if is_annulled:
            if self.client_id and self.client.name != 'ANULADO':
                errors['transaction_type'] = "Para transacciones de anulación, el nombre o razón social debe ser 'ANULADO' y todos los montos deben ser iguales a 0.00."
            
            amounts_to_check = [
                self.total_sales_inc_vat, self.exempt_internal_sales, self.exonerated_internal_sales,
                self.non_subject_internal_sales, self.fob_export_value, self.general_tax_base_16,
                self.general_tax_debit_16, self.reduced_tax_base_8, self.reduced_tax_debit_8,
                self.additional_tax_base_31, self.additional_tax_debit_31, self.igtf_tax_base, self.igtf_tax_amount
            ]
            
            if any(val != Decimal('0.00') for val in amounts_to_check if val is not None):
                errors['transaction_type'] = "Para transacciones de anulación, el nombre o razón social debe ser 'ANULADO' y todos los montos deben ser iguales a 0.00."

        # Cálculo IGTF (3%)
        igtf_base = self.igtf_tax_base or Decimal('0.00')
        igtf_amount = self.igtf_tax_amount or Decimal('0.00')
        if igtf_base > Decimal('0.00'):
            if abs((igtf_base * Decimal('0.03')) - igtf_amount) > Decimal('0.01'):
                errors['igtf_tax_amount'] = "El monto de IGTF debe corresponder exactamente al 3% de la base imponible de IGTF declarada."
        elif igtf_base == Decimal('0.00') and igtf_amount > Decimal('0.00'):
            errors['igtf_tax_amount'] = "El monto de IGTF debe corresponder exactamente al 3% de la base imponible de IGTF declarada."

        # Restricción de Fecha Futura
        if self.document_date and self.document_date > timezone.now().date():
            errors['document_date'] = "La fecha del documento no puede ser posterior a la fecha actual del sistema."

        # Comercio Exterior (Valor FOB vs Ventas Internas)
        fob_val = self.fob_export_value or Decimal('0.00')
        if self.sale_type == self.SaleType.EXPORT:
            if fob_val <= Decimal('0.00'):
                errors['fob_export_value'] = "Para operaciones de exportación, el valor FOB debe ser mayor a 0.00 y los campos de ventas internas deben ser 0.00."
            internal_amounts = [
                self.exempt_internal_sales, self.exonerated_internal_sales, self.non_subject_internal_sales,
                self.general_tax_base_16, self.reduced_tax_base_8, self.additional_tax_base_31
            ]
            if any(val != Decimal('0.00') for val in internal_amounts if val is not None):
                errors['sale_type'] = "Para operaciones de exportación, el valor FOB debe ser mayor a 0.00 y los campos de ventas internas deben ser 0.00."
        elif self.sale_type == self.SaleType.INTERNAL:
            if fob_val > Decimal('0.00'):
                errors['fob_export_value'] = "Para operaciones de ventas internas, el valor FOB de exportación debe ser 0.00 o nulo."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        """Persiste el registro garantizando la inmutabilidad y la normalización de datos."""
        # 1. Restricción de Inmutabilidad Fiscal
        if self.pk:
            old_instance = SalesRecord.objects.get(pk=self.pk)
            if old_instance.record_status in [self.RecordStatus.PROCESSED, self.RecordStatus.ANNULLED_PROCESSED]:
                raise ValidationError({
                    '__all__': "No se puede modificar un registro del Libro de Ventas que ya se encuentra en estatus 'Procesado' o 'Anulado Procesado'."
                })

        # 2. Persistencia de Estatus para Anulaciones
        if self.transaction_type == self.TransactionType.ANNULMENT:
            self.record_status = self.RecordStatus.ANNULLED

        # 3. Normalización Implícita Grupo A
        if self.document_type:
            self.invoice_number = None
            self.last_receipt_number = None
            self.fiscal_printer_number = None
            self.z_report_number = None
            if self.document_type == self.DocumentType.INVOICE:
                self.affected_invoice = None
                
        # 4. Normalización Implícita Grupo B (Mutuamente excluyente al Grupo A)
        elif self.invoice_number or self.fiscal_printer_number or self.z_report_number:
            self.document_type = None
            self.document_number = None
            self.control_number = None
            self.affected_invoice = None

        super().save(*args, **kwargs)