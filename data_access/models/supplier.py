"""Módulo de persistencia para la gestión de proveedores locales.

Define el modelo ProveedorLocal con sus atributos fiscales y legales
específicos para la región, garantizando la consistencia multitenant.
"""

from decimal import Decimal
from typing import Any, Optional
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, RegexValidator, MinValueValidator, MaxValueValidator
from django.db import models

from data_access.models.base import FiscalModuleAbstractModel, FiscalProfile

# Validador de formato oficial para el RIF del proveedor (Capa de Modelado)
rif_format_regex = RegexValidator(
    regex=r'^[VEJGPC]\d{8,9}$',
    message="El RIF debe comenzar estrictamente con una letra mayúscula válida (V, E, J, G, P, C) seguida de 8 a 9 dígitos numéricos, sin guiones ni espacios.",
    code="invalid_supplier_rif"
)


class LocalSupplier(FiscalModuleAbstractModel):
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
        NATURAL = "NATURAL", "Natural Person"
    
    class VatWithholdingPercentageChoices(Decimal, models.Choices):
        """Porcentajes permitidos de retención de IVA según la normativa del SENIAT."""

        ZERO = Decimal('0.00'), "0%"
        SEVENTY_FIVE = Decimal('75.00'), "75%"
        ONE_HUNDRED = Decimal('100.00'), "100%"

    name = models.CharField(
        max_length=255,
        blank=False,  
        validators=[MinLengthValidator(limit_value=1)],  
        verbose_name="Nombre del Proveedor"
    )
    rif = models.CharField(
        max_length=20,
        blank=False,  
        validators=[MinLengthValidator(limit_value=1), rif_format_regex], 
        verbose_name="Registro de Información Fiscal (RIF)"
    )
    supplier_type = models.CharField(
        max_length=20,
        blank=False,
        choices=SupplierType.choices,
        default=SupplierType.WITH_RIF,
        verbose_name="Supplier Type",
        validators=[MinLengthValidator(1, message="El campo no puede estar vacío.")]
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
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00'))
        ],
        verbose_name="ARI Percentage (ISLR)",
    )

    def clean(self) -> None:
        """Ejecuta la sanitización de cadenas y las reglas de negocio condicionales del modelo.

        Normaliza el RIF eliminando espacios y forzando mayúsculas, remueve espacios vacíos
        en el nombre del proveedor, y valida que los porcentajes de retención obligatorios
        estén presentes según el tipo legal de entidad.

        Raises:
            ValidationError: Si falla la estructura del RIF sanitizado o si se omite el
            porcentaje ARI siendo una Persona Natural.
        """
        super().clean()
        errors: dict[str, str] = {}

        # 2.A. Sanitización y Normalización de Datos
        # [rif_clean] - Normalización del RIF del proveedor
        if self.rif:
            self.rif = self.rif.replace(" ", "").upper()
            try:
                rif_format_regex(self.rif)
            except ValidationError as e:
                errors["rif"] = e.messages

        # [name_clean] - Remoción de espacios muertos
        if self.name:
            self.name = self.name.strip()

        # 2.B. Reglas de Negocio Cruzadas
        # [ari_conditional_required] - Validación condicional de obligatoriedad de ARI
        if self.supplier_type == self.SupplierType.NATURAL and self.ari_percentage is None:
            errors["ari_percentage"] = "La ley requiere especificar el porcentaje ARI para proveedores configurados como Persona Natural."

        if errors:
            raise ValidationError(errors)

    class Meta:
        """Configuración de metadatos del modelo LocalSupplier."""
    
        verbose_name = "Local Supplier"
        verbose_name_plural = "Local Suppliers"
            
        constraints = [
            # 1. Restricciones de Unicidad (Aislamiento Multitenant)
            models.UniqueConstraint(
                fields=["fiscal_profile", "rif"],
                name="%(app_label)s_%(class)s_unique_profile_rif"
            ),
            # 2. Restricciones de Integridad de Datos
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="%(app_label)s_%(class)s_name_not_empty"
            ),
            models.CheckConstraint(
                condition=~models.Q(rif=""),
                name="%(app_label)s_%(class)s_rif_not_empty"
            ),
            # Restricciones añadidas por requerimiento impositivo
            models.CheckConstraint(
                condition=models.Q(ari_percentage__isnull=True) | models.Q(ari_percentage__gte=0, ari_percentage__lte=100),
                name="%(app_label)s_%(class)s_ari_percentage_range"
            ),
        ]
    
    def __str__(self) -> str:
        """Retorna una representación legible del Proveedor Local."""
        return f"{self.name} ({self.rif}) - {self.pk}"
    