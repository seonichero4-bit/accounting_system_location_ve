"""Módulo de persistencia para comprobantes de retención fiscal.

Define los modelos legales localizados para gestionar las retenciones preventivas
de IVA (Impuesto al Valor Agregado) e ISLR (Impuesto Sobre la Renta) vinculadas
al libro de compras multi-inquilino.
"""

from django.db import models
from data_access.models.base import FiscalModuleAbstractModel
from data_access.models.purchase_book import PurchaseLedgerInvoice, PurchaseInvoiceLine


class VatWithholdingCertificate(FiscalModuleAbstractModel):
    """Modelo legal para el registro de comprobantes de retención de IVA.

    Establece un vínculo unívoco e inseparabe con una factura de compra del libro
    fiscal, resguardando la integridad de la recaudación del tributo.
    """

    purchase_invoice = models.OneToOneField(
        PurchaseLedgerInvoice,
        on_delete=models.PROTECT,
        related_name="vat_withholding_certificate",
        verbose_name="Associated Purchase Invoice",
    )
    application_date = models.DateField(
        verbose_name="Fiscal Application Date",
    )
    vat_withholding_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="VAT Withholding Percentage (%)",
    )
    certificate_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Withholding Certificate Number",
    )
    vat_withheld_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="VAT Withheld Amount",
    )

    class Meta:
        """Configuración de metadatos del modelo ComprobanteRetencionIVA."""

        verbose_name = "VAT Withholding Certificate"
        verbose_name_plural = "VAT Withholding Certificates"

    def __str__(self) -> str:
        """Retorna una representación legible del comprobante de IVA."""
        return f"VAT Certificate No. {self.certificate_number}"


class IslrWithholdingCertificate(FiscalModuleAbstractModel):
    """Modelo de control para comprobantes de retención de ISLR.

    Asocia las retenciones del Impuesto Sobre la Renta ejecutadas sobre conceptos y
    líneas operativas específicas desglosadas en las compras del período.
    """

    purchase_invoice = models.ForeignKey(
        PurchaseLedgerInvoice,
        on_delete=models.PROTECT,
        related_name="islr_withholding_certificates",
        verbose_name="Related Purchase Invoice",
    )
    source_line = models.OneToOneField(
        PurchaseInvoiceLine,
        on_delete=models.PROTECT,
        related_name="islr_withholding_certificate",
        verbose_name="Source Invoice Line",
    )
    certificate_number = models.CharField(
        max_length=50,
        verbose_name="ISLR Certificate Number",
    )
    closing_day_month = models.CharField(
        max_length=10,
        verbose_name="Closing Day/Month",
    )
    line_taxable_base = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Line Taxable Base",
    )
    applied_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Applied Rate (%)",
    )
    islr_withheld_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="ISLR Withheld Amount",
    )

    class Meta:
        """Configuración de metadatos del modelo ComprobanteRetencionISLR."""

        verbose_name = "ISLR Withholding Certificate"
        verbose_name_plural = "ISLR Withholding Certificates"

    def __str__(self) -> str:
        """Retorna una representación legible del comprobante de ISLR."""
        return f"ISLR Certificate No. {self.certificate_number} (Line ID: {self.source_line_id})"