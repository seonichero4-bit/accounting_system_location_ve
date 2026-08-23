"""Módulo de persistencia para el libro de compras fiscal.

Define los modelos estructurados para el encabezado de las facturas de compra
y sus respectivas líneas de detalle, integrando el control fiscal y el aislamiento
multitenant requerido[cite: 1].
"""

import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator
from django.db import models

from data_access.models.base import FiscalModuleAbstractModel
from data_access.models.supplier import LocalSupplier


class PurchaseLedgerInvoice(FiscalModuleAbstractModel):
    """Modelo para la gestión del encabezado del libro de compras fiscal.

    Almacena los metadatos globales, identificadores de impresión obligatorios,
    fechas de aplicación impositiva y los agregados financieros de una transacción
    de compra[cite: 1].
    """
    class Deductibility(models.TextChoices):
            """Opciones de deducibilidad de credito fiscal."""
            DEDUCIBLE = "Deducible"
            PARCIALMENTE_DEDUCIBLE = "Parcialmente deducible"
            NO_DEDUCIBLE = "No deducible"

    class TransactionType(models.TextChoices):
        """Opciones de porcentaje de IVA según la legislación venezolana."""
        REGISTRO = "01 Registro"
        COMPLEMENTO = "02 Complemento"
        ANULACION = "03 Anulación"
        AJUSTE = "04 Ajuste"

    class InvoiceCategory(models.TextChoices):
        """Opciones de porcentaje de IVA según la legislación venezolana[cite: 1]."""
        INVENTARIO = "INVENTARIO", "Adquisicion de mercancia para el inventario"
        BIENES = "BIENES", "Adquisicion de bienes (Gastos)"
        SERVICIO = "SERVICIO", "Adquisicion de servicio"
        SERVICIO_MIXTO = "SERVICIO_MIXTO", "Adquisicion de servicio bienes (Misma factura)"

    class VatPercentageChoices(models.IntegerChoices):
        """Opciones de porcentaje de IVA según la legislación venezolana[cite: 1]."""
        GENERAL = 1, "Alícuota General (16%)"
        REDUCIDA = 2, "Alícuota Reducida (8%)"
        ADICIONAL = 3, "Alícuota Adicional (31%)"

        @property
        def as_decimal(self) -> Decimal:
            """Retorna el porcentaje en formato Decimal para cálculos[cite: 1]."""
            _mapping = {
                1: Decimal("16.00"),
                2: Decimal("8.00"),
                3: Decimal("31.00"),
            }
            return _mapping[self.value]
            
    class InvoiceStatus(models.TextChoices):
        """Estados operativos y fiscales de la factura[cite: 1]."""
        PRELIMINARY = "PRELIMINARY", "Preliminary"
        PROCESSED = "PROCESSED", "Processed"
        ANULLED = "ANULLED", "ANULLED"
        ANULLED_PROCESSED = "ANULLED_PROCESSED", "ANULLED_PROCESSED"

    class DocumentType(models.TextChoices):
        """Tipos de documentos fiscales soportados en el libro de compras[cite: 1]."""
        INVOICE = "INVOICE", "Invoice"
        CREDIT_NOTE = "CREDIT_NOTE", "Credit Note"
        DEBIT_NOTE = "DEBIT_NOTE", "Debit Note"

    class PurchaseType(models.TextChoices):
        """Clasificación del origen de la compra[cite: 1]."""
        INTERNAL = "INTERNAL", "Internal"
        IMPORT = "IMPORT", "Import"

    # Validadores de campos
    number_validator = RegexValidator(
        regex=r"^[0-9A-Za-z\-]+$",
        message="El número de factura solo debe contener caracteres alfanuméricos estándar y guiones."
    )
    
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        default=TransactionType.REGISTRO,
        verbose_name="transaction type",
    )
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.INVOICE,
        verbose_name="Document Type",
    )
    number = models.CharField(
        max_length=50,
        validators=[number_validator],
        verbose_name="Document Number",
    )
    invoice_control = models.CharField(
        max_length=50,
        validators=[number_validator],
        verbose_name="Invoice Control Number",
    )
    supplier = models.ForeignKey(
        LocalSupplier,
        on_delete=models.PROTECT,
        related_name="purchase_invoices",
        verbose_name="Local Supplier",
    )

    # Fechas y Periodos
    date = models.DateField(
        verbose_name="Issue Date",
    )
    fiscal_period = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fiscal Period(DD-MM-YYYY)",
    )
    # Controles Operativos e Importación
    purchase_type = models.CharField(
        max_length=20,
        choices=PurchaseType.choices,
        default=PurchaseType.INTERNAL,
        verbose_name="Purchase Type",
    )
    import_form_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Import Form Number",
    )
    import_file_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Import File Number",
    )
    affected_invoice = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_debit_notes",
        verbose_name="Affected Invoice (Credit/Debit Notes)",
    )
    # Amount
    exempt_amount = models.DecimalField(
        validators=[MinValueValidator(Decimal('0.00'))],
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Exempt Amount",
    )
    amount_exonerated = models.DecimalField(
        validators=[MinValueValidator(Decimal('0.00'))],
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Amount exonerated",
    )
    amount_not_subject = models.DecimalField(
        validators=[MinValueValidator(Decimal('0.00'))],
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Amount not subject",
    )
    amount_without_right_to_credit = models.DecimalField(
        validators=[MinValueValidator(Decimal('0.00'))],
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Amount without right to credit",
    )
    #subtotales
    taxable_base = models.DecimalField(
        validators=[MinValueValidator(Decimal('0.00'))],
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Taxable Base",
    )
    subtotal = models.DecimalField(
        validators=[MinValueValidator(Decimal('0.00'))],
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Sub Total",
    )
    vat_percentage = models.PositiveSmallIntegerField(
        choices=VatPercentageChoices.choices,
        default=VatPercentageChoices.GENERAL,
        verbose_name="General Tax Rate (%)",
    )
    vat_amount = models.DecimalField(
        validators=[MinValueValidator(Decimal('0.00'))],
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="VAT Amount",
    )
    igtf_base = models.DecimalField(
        validators=[MinValueValidator(Decimal('0.00'))],
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="IGTF Base",
    )
    igtf_amount = models.DecimalField(
        validators=[MinValueValidator(Decimal('0.00'))],
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="IGTF Amount",
    )
    total_purchase = models.DecimalField(
        validators=[MinValueValidator(Decimal('0.00'))],
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Total Purchase",
    )


    # Control de Flujo del Ciclo de Vida
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.PRELIMINARY,
        verbose_name="Invoice Status",
    )
    invoicecategory = models.CharField(
        max_length=20,
        choices=InvoiceCategory.choices,
        default=InvoiceCategory.INVENTARIO,
        verbose_name="Invoice category",
    )
    affected_account = models.JSONField(
        default=list,
        verbose_name="Cuentas de gasto imputadas",                                     
    )
    deductibility = models.CharField(
        max_length=25,
        choices=Deductibility.choices,
        default=Deductibility.DEDUCIBLE,
        verbose_name="Deducibilidad del credito fiscal",
        )
    
    def clean(self) -> None:
        """Realiza las validaciones cruzadas y de temporalidad fiscal del documento.

        Raises:
            ValidationError: Si se violan los flujos de negocio definidos para notas
                             de ajuste, importaciones, temporalidad o inconsistencias de IGTF.
        """
        super().clean()
        errors: dict[str, str] = {}

        # Saneamiento y Normalización del Campo Number
        if self.number:
            self.number = self.number.strip().upper()

        # Soporte para Documentos Anulados (Ciclo de Vida)
        if self.status == self.InvoiceStatus.ANULLED:
            self.exempt_amount = Decimal("0.00")
            self.taxable_base = Decimal("0.00")
            self.subtotal = Decimal("0.00")
            self.vat_amount = Decimal("0.00")
            self.igtf_base = Decimal("0.00")
            self.igtf_amount = Decimal("0.00")
            self.total_purchase = Decimal("0.00")
            return

        # Coherencia Relacional (Notas de Crédito y Débito)
        is_note = self.document_type in [self.DocumentType.CREDIT_NOTE, self.DocumentType.DEBIT_NOTE]
        if is_note or self.affected_invoice:
            if not self.affected_invoice:
                errors["affected_invoice"] = (
                    "El campo de factura afectada es estrictamente obligatorio para notas de crédito o débito."
                )
            else:
                if self.supplier != self.affected_invoice.supplier:
                    errors["supplier"] = "El proveedor de la nota debe ser idéntico al de la factura afectada."
                
                if getattr(self, "fiscal_profile", None) != getattr(self.affected_invoice, "fiscal_profile", None):
                    errors["affected_invoice"] = "La factura afectada debe pertenecer al mismo perfil fiscal multi-tenant."
                
                if self.date and self.affected_invoice.date and self.date < self.affected_invoice.date:
                    errors["date"] = "La fecha de la nota no puede ser cronológicamente anterior a la de la factura afectada."
        elif self.document_type == self.DocumentType.INVOICE:
            self.affected_invoice = None

        # Condicional de Compras de Importación
        if self.purchase_type == self.PurchaseType.IMPORT:
            if not self.import_form_number:
                errors["import_form_number"] = "El número de formulario de importación es obligatorio para compras externas."
            if not self.import_file_number:
                errors["import_file_number"] = "El número de expediente de importación es obligatorio para compras externas."
            else: 
                self.invoice_control = "N/A"

        elif self.purchase_type == self.PurchaseType.INTERNAL:
            self.import_form_number = None
            self.import_file_number = None

        # Coherencia Temporal e Histórica de Fechas y Períodos
        if self.date and self.date > date.today():
            errors["date"] = "La fecha de emisión no puede ser posterior a la fecha actual del sistema."

        # Validación de caducidad de crédito fiscal (Máximo 12 meses)
        if self.date and getattr(self, 'fiscal_period', None):
            meses_diferencia = (self.fiscal_period.year - self.date.year) * 12 + (self.fiscal_period.month - self.date.month)
            if meses_diferencia > 12:
                errors["date"] = "Caducidad de crédito fiscal: La diferencia entre la fecha del documento y el periodo fiscal supera los 12 meses."

    # Validacion aritmetica total_purchase y vat_amount
                
        # Sanitización y extracción de valores numéricos base
        taxable_base = self.taxable_base or Decimal("0.00")
        exempt_amount = self.exempt_amount or Decimal("0.00")
        amount_exonerated = self.amount_exonerated or Decimal("0.00")
        amount_not_subject = self.amount_not_subject or Decimal("0.00")
        amount_without_right_to_credit = self.amount_without_right_to_credit or Decimal("0.00")
        vat_amount = self.vat_amount or Decimal("0.00")
        igtf_base = self.igtf_base or Decimal("0.00")
        igtf_amount = self.igtf_amount or Decimal("0.00")
        total_purchase = self.total_purchase or Decimal("0.00")

        # Consistencia Financiera e IGTF (3%)
        igtf_amt = Decimal(str(igtf_amount))
        igtf_bs = Decimal(str(igtf_base))
        tentative_subtotal = Decimal(str(self.exempt_amount)) + Decimal(str(self.taxable_base))
        
        if igtf_amt > 0 or igtf_bs > 0:
            if not (igtf_amt > 0 and igtf_bs > 0):
                errors["igtf_amount"] = "Interdependencia: Si igtf_amount > 0, igtf_base debe ser mayor a 0, y viceversa."
            else:
                expected_igtf = (igtf_bs * Decimal("0.03")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if abs(igtf_amt - expected_igtf) > Decimal("0.01"):
                    errors["igtf_amount"] = f"La tasa calculada del IGTF debe corresponder al 3% de la base ({expected_igtf})."
                        
                if igtf_bs > tentative_subtotal:
                    errors["igtf_base"] = "El monto máximo de la base IGTF no puede ser superior al subtotal bruto antes de impuestos."

        # VALIDACIÓN: CUADRATURA ARITMÉTICA DEL MONTO DE IVA ---
        if self.vat_percentage is not None:
            try:
                # Se mapea el entero guardado con las opciones del enum fiscal
                vat_choice = self.VatPercentageChoices(self.vat_percentage)
                vat_rate = vat_choice.as_decimal  # Retorna el porcentaje (ej: 16.00)
            except ValueError:
                vat_rate = Decimal("0.00")

            # Cálculo teórico del IVA aplicando el redondeo regulado por ley
            expected_vat = (taxable_base * (vat_rate / Decimal("100.00"))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            if abs(vat_amount - expected_vat) > Decimal("0.01"):
                errors["vat_amount"] = (
                    f"El monto de IVA ingresado ({vat_amount}) discrepa de la "
                    f"alícuota teórica calculada ({expected_vat}) para la base {taxable_base}."
                )

        # VALIDACIÓN: CUADRATURA ARITMÉTICA DEL TOTAL GENERAL ---
        expected_total = (
            exempt_amount + 
            amount_exonerated + 
            amount_not_subject + 
            amount_without_right_to_credit + 
            taxable_base + 
            vat_amount + 
            igtf_amount
        )
        if abs(total_purchase - expected_total) > Decimal("0.01"):
            errors["total_purchase"] = (
                f"El total de compra ({total_purchase}) no coincide con la suma "
                f"aritmética de sus componentes ({expected_total})."
            )
        if errors:
            raise ValidationError(errors)
        
    def save(self, *args: Any, **kwargs: Any) -> None:
        """Guarda la instancia automatizando cálculos financieros y protegiendo registros procesados[cite: 1].

        Raises:
            ValidationError: Si se intenta modificar un registro con estado PROCESSED[cite: 1].
        """
     # Restriccion de eliminacion de documentos procesados
        if self.pk:
            original = PurchaseLedgerInvoice.objects.get(pk=self.pk)
            if original.status == PurchaseLedgerInvoice.InvoiceStatus.PROCESSED:
                raise ValidationError(
                    "Bloqueo de Modificación Fiscal: Un documento en estado PROCESSED es estrictamente de solo lectura."
                )

        if self.status == self.InvoiceStatus.ANULLED:
            self.exempt_amount = Decimal("0.00")
            self.taxable_base = Decimal("0.00")
            self.subtotal = Decimal("0.00")
            self.vat_amount = Decimal("0.00")
            self.igtf_base = Decimal("0.00")
            self.igtf_amount = Decimal("0.00")
            self.total_purchase = Decimal("0.00")
    
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        """Evita la eliminación física de un documento si ya fue procesado y declarado fiscalmente[cite: 1].

        Raises:
            ValidationError: Si el estado actual es PROCESSED o ANULLED.
        """
    # Restriccion de eliminacion de documentos procesados
        if self.status == self.InvoiceStatus.PROCESSED:
            raise ValidationError(
                "Bloqueo de Eliminación Fiscal: No es posible eliminar un documento en estado PROCESSED."
            )
        
        if self.status == self.InvoiceStatus.ANULLED_PROCESSED:
            raise ValidationError(
                "Bloqueo de Eliminación Fiscal: No es posible eliminar un documento en estado ANULLED_PROCESSED."
            )
        return super().delete(*args, **kwargs)

    class Meta:
        """Configuración de metadatos y restricciones a nivel de base de datos."""

        verbose_name = "Purchase Ledger Invoice"
        verbose_name_plural = "Purchase Ledger Invoices"

        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "invoice_control", "document_type", "fiscal_profile"],
                name="unique_supplier_control_document",
            ),
            models.CheckConstraint(
                condition=models.Q(exempt_amount__gte=0),
                name="purchase_invoice_exempt_amount_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(taxable_base__gte=0),
                name="purchase_invoice_taxable_base_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(vat_amount__gte=0),
                name="purchase_invoice_vat_amount_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(igtf_amount__gte=0),
                name="purchase_invoice_igtf_amount_not_negative",
            ),
            # Validación Cruzada de Importación
            models.CheckConstraint(
                condition=~models.Q(purchase_type="IMPORT") | (
                    models.Q(import_form_number__isnull=False) & models.Q(import_file_number__isnull=False)
                ),
                name="purchase_invoice_import_fields_required",
            ),
            # Validación de Nota de Ajuste
            models.CheckConstraint(
                condition=models.Q(document_type="INVOICE") | models.Q(affected_invoice__isnull=False),
                name="purchase_invoice_notes_affected_invoice_required",
            ),
        ]

    def __str__(self) -> str:
        return f"Factura N° {self.number} ({self.invoice_control}) - ID: {self.pk}"