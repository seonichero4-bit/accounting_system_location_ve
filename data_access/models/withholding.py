"""Módulo de persistencia para comprobantes de retención fiscal.

Define los modelos legales localizados para gestionar las retenciones preventivas
de IVA (Impuesto al Valor Agregado) e ISLR (Impuesto Sobre la Renta) vinculadas
al libro de compras multi-inquilino.
"""

from django.db import models
from accounting_system_ve.data_access.models.base import FiscalModuleAbstractModel
from accounting_system_ve.data_access.models.purchase_book import LibroComprasFactura, LineaFacturaCompra


class ComprobanteRetencionIVA(FiscalModuleAbstractModel):
    """Modelo legal para el registro de comprobantes de retención de IVA.

    Establece un vínculo unívoco e inseparabe con una factura de compra del libro
    fiscal, resguardando la integridad de la recaudación del tributo.
    """

    factura_compra = models.OneToOneField(
        LibroComprasFactura,
        on_delete=models.PROTECT,
        related_name="comprobante_iva",
        verbose_name="Factura de Compra Asociada",
    )
    fecha_aplicacion = models.DateField(
        verbose_name="Fecha de Aplicación Fiscal",
    )
    porcentaje_retencion_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Porcentaje de Retención IVA (%)",
    )
    numero_comprobante = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Número de Comprobante de Retención",
    )
    monto_iva_retenido = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Monto de IVA Retenido",
    )

    class Meta:
        """Configuración de metadatos del modelo ComprobanteRetencionIVA."""

        verbose_name = "Comprobante de Retención de IVA"
        verbose_name_plural = "Comprobantes de Retención de IVA"

    def __str__(self) -> str:
        """Retorna una representación legible del comprobante de IVA."""
        return f"Comprobante IVA N° {self.numero_comprobante}"


class ComprobanteRetencionISLR(FiscalModuleAbstractModel):
    """Modelo de control para comprobantes de retención de ISLR.

    Asocia las retenciones del Impuesto Sobre la Renta ejecutadas sobre conceptos y
    líneas operativas específicas desglosadas en las compras del período.
    """

    factura_compra = models.ForeignKey(
        LibroComprasFactura,
        on_delete=models.PROTECT,
        related_name="comprobantes_islr",
        verbose_name="Factura de Compra Relacionada",
    )
    linea_origen = models.OneToOneField(
        LineaFacturaCompra,
        on_delete=models.PROTECT,
        related_name="comprobante_islr",
        verbose_name="Línea de Factura de Origen",
    )
    numero_comprobante = models.CharField(
        max_length=50,
        verbose_name="Número de Comprobante ISLR",
    )
    dia_mes_cierre = models.CharField(
        max_length=10,
        verbose_name="Día/Mes de Cierre",
    )
    base_imponible_linea = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Base Imponible de la Línea",
    )
    alicuota_aplicada = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Alícuota Aplicada (%)",
    )
    monto_islr_retenido = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Monto ISLR Retenido",
    )

    class Meta:
        """Configuración de metadatos del modelo ComprobanteRetencionISLR."""

        verbose_name = "Comprobante de Retención de ISLR"
        verbose_name_plural = "Comprobantes de Retención de ISLR"

    def __str__(self) -> str:
        """Retorna una representación legible del comprobante de ISLR."""
        return f"Comprobante ISLR N° {self.numero_comprobante} (Línea ID: {self.linea_origen_id})"