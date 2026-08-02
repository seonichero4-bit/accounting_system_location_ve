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

# from data_access.mixins.sequence import AutomaticCodeMixin
from data_access.models.base import FiscalModuleAbstractModel
from data_access.models.supplier import LocalSupplier


class PurchaseLedgerInvoice(FiscalModuleAbstractModel):
    """Modelo para la gestión del encabezado del libro de compras fiscal.

    Almacena los metadatos globales, identificadores de impresión obligatorios,
    fechas de aplicación impositiva y los agregados financieros de una transacción
    de compra[cite: 1].
    """
    class InvoiceCategory(models.TextChoices):
        """Opciones de porcentaje de IVA según la legislación venezolana[cite: 1]."""
        INVENTARIO = "INVENTARIO", "Adquisicion de mercancia para el inventario"
        BIENE = "BIENE", "Adquisicion de bienes (Gastos)"
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

    class DocumentType(models.TextChoices):
        """Tipos de documentos fiscales soportados en el libro de compras[cite: 1]."""
        INVOICE = "INVOICE", "Invoice"
        CREDIT_NOTE = "CREDIT_NOTE", "Credit Note"
        DEBIT_NOTE = "DEBIT_NOTE", "Debit Note"

    class PurchaseType(models.TextChoices):
        """Clasificación del origen de la compra[cite: 1]."""
        INTERNAL = "INTERNAL", "Internal"
        IMPORT = "IMPORT", "Import"

    # PREFIX = DocumentType
    # PADDING_LENGTH = 5

    # Validadores de campos
    number_validator = RegexValidator(
        regex=r"^[0-9A-Za-z\-]+$",
        message="El número de factura solo debe contener caracteres alfanuméricos estándar y guiones."
    )

    # code = models.CharField(
    #     max_length=50,
    #     blank=True,
    #     verbose_name="Automatic Sequence Code",
    # )
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
    invoicecategory = models.CharField(
        max_length=20,
        choices=InvoiceCategory.choices,
        default=InvoiceCategory.INVENTARIO,
        verbose_name="Invoice category",
    )
    
    class Meta:
        """Configuración de metadatos y restricciones a nivel de base de datos."""

        verbose_name = "Purchase Ledger Invoice"
        verbose_name_plural = "Purchase Ledger Invoices"

        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "number", "document_type", "fiscal_profile"],
                name="unique_supplier_invoice_document",
            ),
            models.UniqueConstraint(
                fields=["supplier", "invoice_control", "document_type", "fiscal_profile"],
                name="unique_supplier_control_document",
            ),
            # models.UniqueConstraint(
            #     fields=["fiscal_profile", "code"],
            #     name="unique_purchase_invoice_profile_code"
            # ),
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
        
    def clean(self) -> None:
        """Realiza las validaciones cruzadas y de temporalidad fiscal del documento.

        Raises:
            ValidationError: Si se violan los flujos de negocio definidos para notas
                             de ajuste, importaciones, temporalidad o inconsistencias de IGTF.
        """
        super().clean()
        errors: dict[str, str] = {}

        # 0. Saneamiento y Normalización del Campo Number
        if self.number:
            self.number = self.number.strip().upper()

        # 1. Soporte para Documentos Anulados (Ciclo de Vida)
        if self.status == self.InvoiceStatus.ANULLED:
            self.exempt_amount = Decimal("0.00")
            self.taxable_base = Decimal("0.00")
            self.subtotal = Decimal("0.00")
            self.vat_amount = Decimal("0.00")
            self.igtf_base = Decimal("0.00")
            self.igtf_amount = Decimal("0.00")
            self.total_purchase = Decimal("0.00")
            return

        # 2. Coherencia Relacional (Notas de Crédito y Débito)
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

        # 3. Condicional de Compras de Importación
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

        # 4. Coherencia Temporal e Histórica de Fechas y Períodos
        if self.date and self.date > date.today():
            errors["date"] = "La fecha de emisión no puede ser posterior a la fecha actual del sistema."
        # Validacion fecha de pago no sea mayor a la fecha de emicion.
        # if self.payment_date and self.date and self.payment_date < self.date:
        #     errors["payment_date"] = "La fecha de pago debe ser igual o posterior a la fecha de emisión del documento."

        if self.application_month_year:
            if not re.match(r"^(0[1-9]|1[0-2])-\d{4}$", self.application_month_year):
                errors["application_month_year"] = "El formato del período fiscal debe ser estrictamente MM-YYYY."
            else:
                month_str, year_str = self.application_month_year.split("-")
                p_month, p_year = int(month_str), int(year_str)
                today = date.today()

                if p_year > today.year or (p_year == today.year and p_month > today.month):
                    errors["application_month_year"] = "No se permite declarar períodos fiscales futuros que no hayan comenzado."

                if self.date:
                    if p_year < self.date.year or (p_year == self.date.year and p_month < self.date.month):
                        errors["application_month_year"] = (
                            "El período fiscal de aplicación no puede ser cronológicamente anterior a la fecha de emisión."
                        )

                    period_first_day = date(p_year, p_month, 1)
                    months_diff = (period_first_day.year - self.date.year) * 12 + (
                        period_first_day.month - self.date.month
                    )
                    if months_diff > 12:
                        errors["application_month_year"] = (
                            "El derecho al crédito fiscal ha caducado. El período supera los 12 meses desde su emisión (Art. 24 Ley del IVA)."
                        )

        # 5. Consistencia Financiera e IGTF (3%)
        igtf_amt = Decimal(str(self.igtf_amount))
        igtf_bs = Decimal(str(self.igtf_base))
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

        # Validacion aritmetica total_purchase y vat_amount
                
        # Sanitización y extracción de valores numéricos base
        taxable_base = self.taxable_base or Decimal("0.00")
        exempt_amount = self.exempt_amount or Decimal("0.00")
        vat_amount = self.vat_amount or Decimal("0.00")
        igtf_amount = self.igtf_amount or Decimal("0.00")
        total_purchase = self.total_purchase or Decimal("0.00")

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
        expected_total = exempt_amount + taxable_base + vat_amount + igtf_amount

        if abs(total_purchase - expected_total) > Decimal("0.01"):
            errors["total_purchase"] = (
                f"El total de compra ({total_purchase}) no coincide con la suma "
                f"aritmética de sus componentes ({expected_total})."
            )

        # 7. Saneo y Validación del Número de Control
        if self.invoice_control != "N/A"  and self.purchase_type == self.PurchaseType.INTERNAL:
            self.invoice_control = self.invoice_control.strip()
            if not re.match(r"^[0-9A-Za-z\-]+$", self.invoice_control):
                errors["invoice_control"] = "El número de control introducido contiene caracteres especiales o espacios inválidos."

        if errors:
            raise ValidationError(errors)
        
    def save(self, *args: Any, **kwargs: Any) -> None:
        """Guarda la instancia automatizando cálculos financieros y protegiendo registros procesados[cite: 1].

        Raises:
            ValidationError: Si se intenta modificar un registro con estado PROCESSED[cite: 1].
        """
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
        # else:
        #     t_base = Decimal(str(self.taxable_base))
        #     vat_choice = self.VatPercentageChoices(self.vat_percentage)
        #     g_rate = vat_choice.as_decimal
        #     e_amount = Decimal(str(self.exempt_amount))
        #     i_amount = Decimal(str(self.igtf_amount))

        #     self.vat_amount = (t_base * (g_rate / Decimal("100.00"))).quantize(
        #         Decimal("0.01"), rounding=ROUND_HALF_UP
        #     )
        #     self.subtotal = e_amount + t_base
        #     self.total_purchase = self.subtotal + self.vat_amount + i_amount

        # self.handle_automatic_code()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        """Evita la eliminación física de un documento si ya fue procesado y declarado fiscalmente[cite: 1].

        Raises:
            ValidationError: Si el estado actual es PROCESSED o ANULLED.
        """
        if self.status == self.InvoiceStatus.PROCESSED:
            raise ValidationError(
                "Bloqueo de Eliminación Fiscal: No es posible eliminar un documento en estado PROCESSED."
            )
        
        if self.status == self.InvoiceStatus.ANULLED:
            raise ValidationError(
                "Bloqueo de Eliminación Fiscal: No es posible eliminar un documento en estado ANULLED."
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