"""Módulo de persistencia para la gestión de proveedores locales.

Define el modelo ProveedorLocal con sus atributos fiscales y legales
específicos para la región, garantizando la consistencia multitenant.
"""

from decimal import Decimal
from typing import Any
from django.core.exceptions import ValidationError
from django.db import models

from data_access.mixins.sequence import AutomaticCodeMixin
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


class LocalSupplier(AutomaticCodeMixin, FiscalModuleAbstractModel):
    """Modelo para gestionar los metadatos y configuraciones fiscales de proveedores regionales.

    Hereda de FiscalModuleAbstractModel para heredar el aislamiento de inquilino
    mediante el campo obligatorio 'fiscal_profile'. Genera de manera automática
    su código identificador a través de AutomaticCodeMixin.
    """

    class SupplierType(models.TextChoices):
        """Opciones legales para determinar el tipo de proveedor regional."""

        WITH_RIF = "WITH_RIF", "With RIF"
        WITHOUT_RIF = "WITHOUT_RIF", "Without RIF"
        NON_RESIDENT = "NON_RESIDENT", "Non-Resident"
        NON_DOMICILED = "NON_DOMICILED", "Non-Domiciled"
    
    class VatWithholdingPercentageChoices(Decimal, models.Choices):
        """Porcentajes permitidos de retención de IVA según la normativa del SENIAT."""

        ZERO = Decimal('0.00'), "0%"
        SEVENTY_FIVE = Decimal('75.00'), "75%"
        ONE_HUNDRED = Decimal('100.00'), "100%"

    # Configuración de propiedades para el AutomaticCodeMixin
    PREFIX = AutomaticCodeMixin.CodePrefixes.PROVEEDORES
    PADDING_LENGTH = 5

    code = models.CharField(
        max_length=50,
        blank=True,
        editable=False,
        verbose_name="Automatic Sequence Code",
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
        choices=VatWithholdingPercentageChoices.choices,
        default=VatWithholdingPercentageChoices.ZERO,
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
        # Se asegura tanto la unicidad del RIF como la del Código Autogenerado por inquilino
        unique_together = (("fiscal_profile", "rif"), ("fiscal_profile", "code"))

    def __str__(self) -> str:
        """Retorna una representación legible del Proveedor Local."""
        return f"{self.name} ({self.rif}) - {self.code}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Persiste el proveedor ejecutando la generación automática de códigos."""
        self.handle_automatic_code()
        super().save(*args, **kwargs)