"""Módulo de persistencia para el libro de compras fiscal.

Define los modelos estructurados para el encabezado de las facturas de compra
y sus respectivas líneas de detalle, integrando el control fiscal y el aislamiento
multitenant requerido.
"""

import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator
from django.db import models

from data_access.mixins.sequence import AutomaticCodeMixin
from data_access.models.base import FiscalModuleAbstractModel, FiscalProfile
from data_access.models.supplier import LocalSupplier


class PurchaseLedgerInvoice(AutomaticCodeMixin, FiscalModuleAbstractModel):
    """Modelo para la gestión del encabezado del libro de compras fiscal.

    Almacena los metadatos globales, identificadores de impresión obligatorios,
    fechas de aplicación impositiva y los agregados financieros de una transacción
    de compra. Genera de manera automática un código de control secuencial único.
    """
    class VatPercentageChoices(models.IntegerChoices):
        """Opciones de porcentaje de IVA según la legislación venezolana."""
        GENERAL = 1, "Alícuota General (16%)"
        REDUCIDA = 2, "Alícuota Reducida (8%)"
        ADICIONAL = 3, "Alícuota Adicional (31%)"

        @property
        def as_decimal(self) -> Decimal:
            """Retorna el porcentaje en formato Decimal para cálculos."""
            _mapping = {
                1: Decimal("16.00"),
                2: Decimal("8.00"),
                3: Decimal("31.00"),
            }
            return _mapping[self.value]
            
    class InvoiceStatus(models.TextChoices):
        """Estados operativos y fiscales de la factura."""

        PRELIMINARY = "PRELIMINARY", "Preliminary"
        PROCESSED = "PROCESSED", "Processed"
        ANULLED = "ANULLED", "ANULLED"

    class DocumentType(models.TextChoices):
        """Tipos de documentos fiscales soportados en el libro de compras."""

        INVOICE = "INVOICE", "Invoice"
        CREDIT_NOTE = "CREDIT_NOTE", "Credit Note"
        DEBIT_NOTE = "DEBIT_NOTE", "Debit Note"

    class PurchaseType(models.TextChoices):
        """Clasificación del origen de la compra."""

        INTERNAL = "INTERNAL", "Internal"
        IMPORT = "IMPORT", "Import"

    # Configuración de propiedades para el AutomaticCodeMixin
    PREFIX = "FACTURA_COMPRA"  
    PADDING_LENGTH = 5

    code = models.CharField(
        max_length=50,
        blank=True,
        editable=True, #En produccion es False
        verbose_name="Automatic Sequence Code",
    )

    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.INVOICE,
        verbose_name="Document Type",
    )
    number = models.CharField(
        max_length=50,
        verbose_name="Document Number",
    )
    invoice_control = models.CharField(
        max_length=50,
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
    payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Payment Date",
    )
    application_month_year = models.CharField(
        max_length=7,
        verbose_name="Application Month and Year (MM-YYYY)",
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
    transaction_type = models.CharField(
        max_length=50,
        verbose_name="Transaction Type",
    )
    affected_invoice = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_debit_notes",
        verbose_name="Affected Invoice (Credit/Debit Notes)",
    )
    exempt_amount = models.DecimalField(
        validators=[MinValueValidator(Decimal('0.00'))],
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Exempt Amount",
    )
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
        max_length=15,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.PRELIMINARY,
        verbose_name="Invoice Status",
    )
    
    class Meta:
        """Configuración de metadatos y restricciones a nivel de base de datos."""

        verbose_name = "Purchase Ledger Invoice"
        verbose_name_plural = "Purchase Ledger Invoices"

        constraints = [
            # Unicidad de Facturas por Proveedor
            models.UniqueConstraint(
                fields=["supplier", "number", "document_type", "fiscal_profile"],
                name="unique_supplier_invoice_document",
            ),
            # Unicidad de Control por Proveedor
            models.UniqueConstraint(
                fields=["supplier", "invoice_control", "document_type", "fiscal_profile"],
                name="unique_supplier_control_document",
            ),
            # Migración de unique_together anterior a UniqueConstraint moderna
            models.UniqueConstraint(
                fields=["fiscal_profile", "code"],
                name="unique_purchase_invoice_profile_code"
            ),
            # Validación de Valores No Negativos en Campos Financieros
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
        ]
        
    def clean(self) -> None:
        """Realiza las validaciones cruzadas y de temporalidad fiscal del documento.

        Raises:
            ValidationError: Si se violan los flujos de negocio definidos para notas
                             de ajuste, importaciones, temporalidad o caducidad fiscal.
        """
        super().clean()
        errors: dict[str, str] = {}

        # 1. Condicional de Notas de Crédito/Débito
        if self.document_type in [PurchaseLedgerInvoice.DocumentType.CREDIT_NOTE, PurchaseLedgerInvoice.DocumentType.DEBIT_NOTE]:
            if not self.affected_invoice:
                errors["affected_invoice"] = (
                    "El campo de factura afectada es estrictamente obligatorio para notas de crédito o débito."
                )
        elif self.document_type == PurchaseLedgerInvoice.DocumentType.INVOICE:
            self.affected_invoice = None

        # 2. Condicional de Compras de Importación
        if self.purchase_type == PurchaseLedgerInvoice.PurchaseType.IMPORT:
            if not self.import_form_number:
                errors["import_form_number"] = (
                    "El número de formulario de importación es obligatorio para compras externas."
                )
            if not self.import_file_number:
                errors["import_file_number"] = (
                    "El número de expediente de importación es obligatorio para compras externas."
                )
        elif self.purchase_type == PurchaseLedgerInvoice.PurchaseType.INTERNAL:
            self.import_form_number = None
            self.import_file_number = None

        # 3. Coherencia Temporal (Fechas futuras)
        if self.date and self.date > date.today():
            errors["date"] = "La fecha de emisión no puede ser posterior a la fecha actual del sistema."

        # 4. Validación del Período Fiscal (application_month_year)
        if self.application_month_year:
            if not re.match(r"^(0[1-9]|1[0-2])-\d{4}$", self.application_month_year):
                errors["application_month_year"] = "El formato del período fiscal debe ser estrictamente MM-YYYY."
            else:
                month_str, year_str = self.application_month_year.split("-")
                p_month, p_year = int(month_str), int(year_str)

                if self.date:
                    if p_year < self.date.year or (p_year == self.date.year and p_month < self.date.month):
                        errors["application_month_year"] = (
                            "El período fiscal de aplicación no puede ser cronológicamente anterior a la fecha de emisión."
                        )

                    # Caducidad del Crédito Fiscal (Art. 24 Ley del IVA)
                    period_first_day = date(p_year, p_month, 1)
                    months_diff = (period_first_day.year - self.date.year) * 12 + (
                        period_first_day.month - self.date.month
                    )
                    if months_diff > 12:
                        errors["application_month_year"] = (
                            "El derecho al crédito fiscal ha caducado. El período supera los 12 meses desde su emisión (Art. 24 Ley del IVA)."
                        )

        if errors:
            raise ValidationError(errors)
            
        # 5. Sanea y valida el formato del número de control de imprenta nacional
        if self.invoice_control:
            # Saneamiento (Normalización de espacios en los extremos)
            self.invoice_control = self.invoice_control.strip()
            
            # Validación de caracteres permitidos (Alfanuméricos y guiones)
            if not re.match(r"^[0-9A-Za-z\-]+$", self.invoice_control):
                errors["invoice_control"] = (
                    "El número de control introducido contiene caracteres especiales o espacios inválidos."
                )

        if errors:
            raise ValidationError(errors)
        
    def save(self, *args: Any, **kwargs: Any) -> None:
        """Guarda la instancia automatizando cálculos financieros y protegiendo registros procesados.

        Raises:
            ValidationError: Si se intenta modificar un registro con estado PROCESSED.
        """
        if self.pk:
            original = PurchaseLedgerInvoice.objects.get(pk=self.pk)
            if original.status == PurchaseLedgerInvoice.InvoiceStatus.PROCESSED:
                raise ValidationError(
                    "Bloqueo de Modificación Fiscal: Un documento en estado PROCESSED es estrictamente de solo lectura."
                )

        # Cálculos Financieros Automatizados con Decimal
        t_base = Decimal(str(self.taxable_base))
        g_rate = Decimal(str(self.vat_percentage.as_decimal))
        e_amount = Decimal(str(self.exempt_amount))
        i_amount = Decimal(str(self.igtf_amount))

        self.vat_amount = (t_base * (g_rate / Decimal("100.00"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self.subtotal = e_amount + t_base
        self.total_purchase = self.subtotal + self.vat_amount + i_amount

        self.handle_automatic_code()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        """Evita la eliminación física de un documento si ya fue procesado y declarado fiscalmente.

        Raises:
            ValidationError: Si el estado actual es PROCESSED.
        """
        if self.status == PurchaseLedgerInvoice.InvoiceStatus.PROCESSED:
            raise ValidationError(
                "Bloqueo de Eliminación Fiscal: No es posible eliminar un documento en estado PROCESSED."
            )
        return super().delete(*args, **kwargs)

    

# class PurchaseInvoiceLine(models.Model):
#     """Modelo operativo para el desglose detallado de los ítems de una compra.

#     Vinculado directamente a un registro del libro de compras mediante una relación
#     de dependencia estricta.
#     """

#     class LineNature(models.TextChoices):
#         """Clasificación legal de los bienes o servicios adquiridos."""

#         GOOD = "GOOD", "Good"
#         SERVICE = "SERVICE", "Service"

#     purchase_invoice = models.ForeignKey(
#         PurchaseLedgerInvoice,
#         on_delete=models.CASCADE,
#         related_name="lines",
#         verbose_name="Associated Purchase Invoice",
#     )
#     description = models.CharField(
#         max_length=255,
#         verbose_name="Item/Service Description",
#     )
#     unit_price = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         verbose_name="Unit Price",
#     )
#     units = models.DecimalField(
#         max_digits=12,
#         decimal_places=4,
#         verbose_name="Units",
#     )
#     discount_percentage = models.DecimalField(
#         max_digits=5,
#         decimal_places=2,
#         default=Decimal("0.00"),
#         verbose_name="Discount Percentage (%)",
#     )
#     subtotal_before_vat = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         verbose_name="Subtotal before VAT",
#     )
#     vat_rate = models.DecimalField(
#         max_digits=5,
#         decimal_places=2,
#         verbose_name="VAT Rate (%)",
#     )
#     line_vat_amount = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         verbose_name="Line VAT Amount",
#     )
#     nature = models.CharField(
#         max_length=10,
#         choices=LineNature.choices,
#         verbose_name="Line Nature",
#     )
#     applies_islr_withholding = models.BooleanField(
#         default=False,
#         verbose_name="Applies ISLR Withholding?",
#     )
#     islr_withholding_percentage = models.DecimalField(
#         max_digits=5,
#         decimal_places=2,
#         default=Decimal("0.00"),
#         verbose_name="ISLR Withholding Percentage (%)",
#     )
#     vectorize_description = models.TextField(
#         null=True,
#         blank=True,
#         verbose_name="Descriptive Text for Semantic Processing / Embeddings",
#     )
#     accounting_mapping = models.CharField(
#         max_length=255,
#         null=True,
#         blank=True,
#         verbose_name="Expense/Inventory Accounting Mapping",
#     )

#     class Meta:
#         """Configuración de metadatos del modelo LineaFacturaCompra."""

#         verbose_name = "Purchase Invoice Line"
#         verbose_name_plural = "Purchase Invoice Lines"

#     def __str__(self) -> str:
#         """Retorna una visualización rápida de la línea operativa."""
#         return f"{self.description} (x{self.units})"