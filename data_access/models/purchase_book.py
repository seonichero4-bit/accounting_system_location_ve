"""Módulo de persistencia para el libro de compras fiscal.

Define los modelos estructurados para el encabezado de las facturas de compra
y sus respectivas líneas de detalle, integrando el control fiscal y el aislamiento
multitenant requerido.
"""

from decimal import Decimal
from django.db import models
from accounting_system_ve.data_access.models.base import FiscalModuleAbstractModel
from accounting_system_ve.data_access.models.supplier import ProveedorLocal


class LibroComprasFactura(FiscalModuleAbstractModel):
    """Modelo para la gestión del encabezado del libro de compras fiscal.

    Almacena los metadatos globales, identificadores de impresión obligatorios,
    fechas de aplicación impositiva y los agregados financieros de una transacción
    de compra.
    """

    class EstadoFactura(models.TextChoices):
        """Estados operativos y fiscales de la factura."""

        PRELIMINAR = "PRELIMINAR", "Preliminar"
        PROCESADA = "PROCESADA", "Procesada"

    class TipoDocumento(models.TextChoices):
        """Tipos de documentos fiscales soportados en el libro de compras."""

        FACTURA = "FACTURA", "Factura"
        NOTA_CREDITO = "NOTA_CREDITO", "Nota de Crédito"
        NOTA_DEBITO = "NOTA_DEBITO", "Nota de Débito"

    class TipoCompra(models.TextChoices):
        """Clasificación del origen de la compra."""

        INTERNA = "INTERNA", "Interna"
        IMPORTACION = "IMPORTACION", "Importación"

    # Identificación y Relaciones
    tipo_documento = models.CharField(
        max_length=20,
        choices=TipoDocumento.choices,
        default=TipoDocumento.FACTURA,
        verbose_name="Tipo de Documento",
    )
    numero = models.CharField(
        max_length=50,
        verbose_name="Número de Documento",
    )
    control_factura = models.CharField(
        max_length=50,
        verbose_name="Número de Control de Factura",
    )
    proveedor = models.ForeignKey(
        ProveedorLocal,
        on_delete=models.PROTECT,
        related_name="facturas_compra",
        verbose_name="Proveedor Local",
    )

    # Fechas y Periodos
    fecha = models.DateField(
        verbose_name="Fecha de Emisión",
    )
    fecha_pago = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Pago",
    )
    mes_ano_aplicacion = models.CharField(
        max_length=7,
        verbose_name="Mes y Año de Aplicación (MM-YYYY)",
    )

    # Controles Operativos e Importación
    tipo_compra = models.CharField(
        max_length=20,
        choices=TipoCompra.choices,
        default=TipoCompra.INTERNA,
        verbose_name="Tipo de Compra",
    )
    numero_planilla_importacion = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Número de Planilla de Importación",
    )
    numero_expediente_importacion = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Número de Expediente de Importación",
    )
    tipo_transaccion = models.CharField(
        max_length=50,
        verbose_name="Tipo de Transacción",
    )
    factura_afectada = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Factura Afectada (Notas de Crédito/Débito)",
    )
    credito_fiscal_tipo = models.CharField(
        max_length=50,
        verbose_name="Tipo de Crédito Fiscal",
    )

    # Integración Contable
    mapeo_contable_retencion_iva = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Mapeo Contable de Retención IVA",
    )

    # Totales y Financieros Globales
    monto_exento = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Monto Exento",
    )
    base_imponible = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Base Imponible",
    )
    sub_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Sub Total",
    )
    tasa_general = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("16.00"),
        verbose_name="Tasa General Alícuota (%)",
    )
    monto_iva = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Monto IVA",
    )
    base_igtf = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Base IGTF",
    )
    monto_igtf = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Monto IGTF",
    )
    total_compra = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Total Compra",
    )

    # Control de Flujo del Ciclo de Vida
    estado = models.CharField(
        max_length=15,
        choices=EstadoFactura.choices,
        default=EstadoFactura.PRELIMINAR,
        verbose_name="Estado de Factura",
    )

    class Meta:
        """Configuración de metadatos del modelo LibroComprasFactura."""

        verbose_name = "Factura de Compra (Libro)"
        verbose_name_plural = "Facturas de Compra (Libro)"

    def __str__(self) -> str:
        """Retorna una representación descriptiva de la factura."""
        return f"{self.tipo_documento} N° {self.numero} - Control {self.control_factura}"


class LineaFacturaCompra(models.Model):
    """Modelo operativo para el desglose detallado de los ítems de una compra.

    Vinculado directamente a un registro del libro de compras mediante una relación
    de dependencia estricta.
    """

    class NaturalezaLinea(models.TextChoices):
        """Clasificación legal de los bienes o servicios adquiridos."""

        BIEN = "BIEN", "Bien"
        SERVICIO = "SERVICIO", "Servicio"

    factura_compra = models.ForeignKey(
        LibroComprasFactura,
        on_delete=models.CASCADE,
        related_name="lineas",
        verbose_name="Factura de Compra Asociada",
    )
    descripcion = models.CharField(
        max_length=255,
        verbose_name="Descripción del Ítems/Servicio",
    )
    precio_unitario = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Precio Unitario",
    )
    unidades = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name="Unidades",
    )
    porcentaje_descuento = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Porcentaje de Descuento (%)",
    )
    subtotal_antes_iva = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Subtotal antes de IVA",
    )
    alicuota_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Alícuota IVA (%)",
    )
    monto_iva_linea = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Monto IVA de la Línea",
    )
    naturaleza = models.CharField(
        max_length=10,
        choices=NaturalezaLinea.choices,
        verbose_name="Naturaleza de la Línea",
    )
    aplica_retencion_islr = models.BooleanField(
        default=False,
        verbose_name="¿Aplica Retención ISLR?",
    )
    porcentaje_retencion_islr = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Porcentaje Retención ISLR (%)",
    )
    descripcion_vectorizar = models.TextField(
        null=True,
        blank=True,
        verbose_name="Texto Descriptivo para Procesamiento Semántico / Embeddings",
    )
    mapeo_contable = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Mapeo Contable de Gasto/Inventario",
    )

    class Meta:
        """Configuración de metadatos del modelo LineaFacturaCompra."""

        verbose_name = "Línea de Factura de Compra"
        verbose_name_plural = "Líneas de Factura de Compra"

    def __str__(self) -> str:
        """Retorna una visualización rápida de la línea operativa."""
        return f"{self.descripcion} (x{self.unidades})"