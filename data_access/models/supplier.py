"""Módulo de persistencia para la gestión de proveedores locales.

Define el modelo ProveedorLocal con sus atributos fiscales y legales
específicos para la región, garantizando la consistencia multitenant.
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from data_access.models.base import FiscalModuleAbstractModel, FiscalProfile


def validate_vat_withholding_percentage(value: Decimal) -> None:
    """Valida que el porcentaje de retención de IVA coincida con los valores legales.

    Args:
        value: El valor decimal a validar.

    Raises:
        ValidationError: Si el valor no es 0.00, 75.00 o 100.00.
    """
    allowed_values = [Decimal("0.00"), Decimal("75.00"), Decimal("100.00")]
    if value not in allowed_values:
        raise ValidationError(
            f"The VAT withholding percentage ({value}) is not valid. "
            f"It must be exactly one of the following values: 0.00, 75.00, or 100.00."
        )


class LocalSupplier(FiscalModuleAbstractModel):
    """Modelo para gestionar los metadatos y configuraciones fiscales de proveedores regionales.

    Hereda de FiscalModuleAbstractModel para heredar el aislamiento de inquilino
    mediante el campo obligatorio 'fiscal_profile'.
    """

    class SupplierType(models.TextChoices):
        """Opciones legales para determinar el tipo de proveedor regional."""

        WITH_RIF = "WITH_RIF", "With RIF"
        WITHOUT_RIF = "WITHOUT_RIF", "Without RIF"
        NON_RESIDENT = "NON_RESIDENT", "Non-Resident"
        NON_DOMICILED = "NON_DOMICILED", "Non-Domiciled"

    fiscal_profile = models.ForeignKey(
        FiscalProfile,
        on_delete=models.CASCADE,
        related_name="local_suppliers",
        verbose_name="Fiscal Profile",
    )    

    code = models.CharField(
        max_length=50,
        verbose_name="Supplier Code",
    )
    name = models.CharField(
        max_length=255,
        verbose_name="Name or Corporate Name",
    )
    rif = models.CharField(
        max_length=20,
        verbose_name="Fiscal Information Registry (RIF)",
    )
    supplier_type = models.CharField(
        max_length=20,
        choices=SupplierType.choices,
        verbose_name="Supplier Type",
    )
    usual_withholding = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Usual Withholding Concept",
    )
    vat_withholding_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_vat_withholding_percentage],
        verbose_name="VAT Withholding Percentage",
    )
    ari_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="ARI Percentage (ISLR)",
    )

    class Meta:
        """Configuración de metadatos del modelo ProveedorLocal."""

        verbose_name = "Local Supplier"
        verbose_name_plural = "Local Suppliers"
        unique_together = ('fiscal_profile', 'rif')

    def __str__(self) -> str:
        """Retorna una representación legible del Proveedor Local."""
        return f"{self.name} ({self.rif})"