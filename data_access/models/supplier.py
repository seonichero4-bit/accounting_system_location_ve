"""Módulo de persistencia para la gestión de proveedores locales.

Define el modelo ProveedorLocal con sus atributos fiscales y legales
específicos para la región, garantizando la consistencia multitenant.
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from accounting_system_ve.data_access.models.base import FiscalModuleAbstractModel, FiscalProfile


def validar_porcentaje_retencion_iva(value: Decimal) -> None:
    """Valida que el porcentaje de retención de IVA coincida con los valores legales.

    Args:
        value: El valor decimal a validar.

    Raises:
        ValidationError: Si el valor no es 0.00, 75.00 o 100.00.
    """
    valores_permitidos = [Decimal("0.00"), Decimal("75.00"), Decimal("100.00")]
    if value not in valores_permitidos:
        raise ValidationError(
            f"El porcentaje de retención de IVA ({value}) no es válido. "
            f"Debe ser exactamente uno de los siguientes valores: 0.00, 75.00 o 100.00."
        )


class ProveedorLocal(FiscalModuleAbstractModel):
    """Modelo para gestionar los metadatos y configuraciones fiscales de proveedores regionales.

    Hereda de FiscalModuleAbstractModel para heredar el aislamiento de inquilino
    mediante el campo obligatorio 'fiscal_profile'.
    """

    class TipoProveedor(models.TextChoices):
        """Opciones legales para determinar el tipo de proveedor regional."""

        CON_RIF = "CON_RIF", "Con RIF"
        SIN_RIF = "SIN_RIF", "Sin RIF"
        NO_RESIDENCIADO = "NO_RESIDENCIADO", "No Residenciado"
        NO_DOMICILIADO = "NO_DOMICILIADO", "No Domiciliado"

    fiscal_profile = models.ForeignKey(
        FiscalProfile,
        on_delete=models.CASCADE,
        related_name="proveedores_locales",
        verbose_name="Perfil Fiscal",
    )    

    codigo = models.CharField(
        max_length=50,
        verbose_name="Código de Proveedor",
    )
    nombre = models.CharField(
        max_length=255,
        verbose_name="Nombre o Razón Social",
    )
    rif = models.CharField(
        max_length=20,
        verbose_name="Registro de Información Fiscal (RIF)",
    )
    tipo_proveedor = models.CharField(
        max_length=20,
        choices=TipoProveedor.choices,
        verbose_name="Tipo de Proveedor",
    )
    retencion_usual = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Concepto de Retención Usual",
    )
    porcentaje_retencion_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validar_porcentaje_retencion_iva],
        verbose_name="Porcentaje de Retención de IVA",
    )
    porcentaje_ari = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Porcentaje ARI (ISLR)",
    )

    class Meta:
        """Configuración de metadatos del modelo ProveedorLocal."""

        verbose_name = "Proveedor Local"
        verbose_name_plural = "Proveedores Locales"
        unique_together = ('fiscal_profile', 'rif')

    def __str__(self) -> str:
        """Retorna una representación legible del Proveedor Local."""
        return f"{self.nombre} ({self.rif})"