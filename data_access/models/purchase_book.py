"""Módulo de persistencia para el libro de compras fiscal.

Define los modelos estructurados para el encabezado de las facturas de compra
y sus respectivas líneas de detalle, integrando el control fiscal y el aislamiento
multitenant requerido.
"""

from decimal import Decimal
from typing import Any
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

    class InvoiceStatus(models.TextChoices):
        """Estados operativos y fiscales de la factura."""

        PRELIMINARY = "PRELIMINARY", "Preliminary"
        PROCESSED = "PROCESSED", "Processed"

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
        editable=False,
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
    affected_invoice = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Affected Invoice (Credit/Debit Notes)",
    )
    tax_credit_type = models.CharField(
        max_length=50,
        verbose_name="Tax Credit Type",
    )

    # Integración Contable
    vat_withholding_accounting_mapping = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="VAT Withholding Accounting Mapping",
    )

    # Totales y Financieros Globales
    exempt_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Exempt Amount",
    )
    taxable_base = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Taxable Base",
    )
    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Sub Total",
    )
    general_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("16.00"),
        verbose_name="General Tax Rate (%)",
    )
    vat_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="VAT Amount",
    )
    igtf_base = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="IGTF Base",
    )
    igtf_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="IGTF Amount",
    )
    total_purchase = models.DecimalField(
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
        """Configuración de metadatos del modelo LibroComprasFactura."""

        verbose_name = "Purchase Invoice (Ledger)"
        verbose_name_plural = "Purchase Invoices (Ledger)"
        unique_together = ("fiscal_profile", "code")

    def __str__(self) -> str:
        """Retorna una representación descriptiva de la factura."""
        return f"{self.document_type} N° {self.number} - Control {self.invoice_control} ({self.code})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Persiste la factura ejecutando la pre-generación automática de códigos."""
        self.handle_automatic_code()
        super().save(*args, **kwargs)


class PurchaseInvoiceLine(models.Model):
    """Modelo operativo para el desglose detallado de los ítems de una compra.

    Vinculado directamente a un registro del libro de compras mediante una relación
    de dependencia estricta.
    """

    class LineNature(models.TextChoices):
        """Clasificación legal de los bienes o servicios adquiridos."""

        GOOD = "GOOD", "Good"
        SERVICE = "SERVICE", "Service"

    purchase_invoice = models.ForeignKey(
        PurchaseLedgerInvoice,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Associated Purchase Invoice",
    )
    description = models.CharField(
        max_length=255,
        verbose_name="Item/Service Description",
    )
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Unit Price",
    )
    units = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name="Units",
    )
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Discount Percentage (%)",
    )
    subtotal_before_vat = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Subtotal before VAT",
    )
    vat_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="VAT Rate (%)",
    )
    line_vat_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Line VAT Amount",
    )
    nature = models.CharField(
        max_length=10,
        choices=LineNature.choices,
        verbose_name="Line Nature",
    )
    applies_islr_withholding = models.BooleanField(
        default=False,
        verbose_name="Applies ISLR Withholding?",
    )
    islr_withholding_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="ISLR Withholding Percentage (%)",
    )
    vectorize_description = models.TextField(
        null=True,
        blank=True,
        verbose_name="Descriptive Text for Semantic Processing / Embeddings",
    )
    accounting_mapping = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Expense/Inventory Accounting Mapping",
    )

    class Meta:
        """Configuración de metadatos del modelo LineaFacturaCompra."""

        verbose_name = "Purchase Invoice Line"
        verbose_name_plural = "Purchase Invoice Lines"

    def __str__(self) -> str:
        """Retorna una visualización rápida de la línea operativa."""
        return f"{self.description} (x{self.units})"