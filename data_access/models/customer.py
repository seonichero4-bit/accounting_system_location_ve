"""Módulo de persistencia para el modelo Customer.

Este módulo define la entidad de Cliente (Customer) asegurando el cumplimiento
de los requisitos fiscales y las validaciones de negocio establecidas
(Artículos 76 al 78 del Reglamento de la LIVA).
"""

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django_ledger.models import AccountModel

from data_access.models.base import FiscalModuleAbstractModel


class Customer(FiscalModuleAbstractModel):
    """Modelo que representa a un cliente o comprador dentro del sistema.

    Hereda de FiscalModuleAbstractModel para garantizar el aislamiento
    multi-inquilino y establece las validaciones tributarias venezolanas.
    """

    class TaxpayerType(models.TextChoices):
        """Enumeración para clasificar los tipos de contribuyentes fiscales."""
        ORDINARY = "ORDINARY", "Ordinario"
        SPECIAL = "SPECIAL", "Especial"
        NON_TAXPAYER = "NON_TAXPAYER", "No Contribuyente"

    rif = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^[VEJGPCvejgpc]\d{8,9}$',
                message="El RIF debe comenzar con V, E, J, G, P, C seguido de 8 a 9 dígitos."
            )
        ],
        verbose_name="RIF"
    )
    name = models.CharField(
        max_length=255,
        verbose_name="Nombre / Razón Social"
    )
    fiscal_address = models.TextField(
        verbose_name="Dirección Fiscal"
    )
    phone_number = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\d{10,11}$',
                message="El número de teléfono debe contener entre 10 y 11 dígitos."
            )
        ],
        verbose_name="Teléfono"
    )
    taxpayer_type = models.CharField(
        max_length=20,
        choices=TaxpayerType.choices,
        default=TaxpayerType.ORDINARY,
        verbose_name="Tipo de Contribuyente"
    )
    custom_accounts_receivable = models.ForeignKey(
        AccountModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_receivable_accounts",
        verbose_name="Cuentas por Cobrar Comerciales"
    )
    custom_income_account = models.ForeignKey(
        AccountModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_income_accounts",
        verbose_name="Ventas de Mercancía General"
    )

    class Meta:
        """Configuraciones de tabla y restricciones a nivel de Base de Datos."""
        constraints = [
            models.UniqueConstraint(
                fields=["rif"],
                name="unique_active_rif_customer",
                violation_error_message="Ya existe un registro activo con este número de RIF en la base de datos."
            ),
            models.CheckConstraint(
                condition=~models.Q(rif="") & ~models.Q(rif__regex=r'^\s+$'),
                name="customer_rif_not_empty",
                violation_error_message="Este campo es obligatorio y no puede quedar vacío ni contener únicamente espacios."
            ),
            models.CheckConstraint(
                condition=~models.Q(name="") & ~models.Q(name__regex=r'^\s+$'),
                name="customer_name_not_empty",
                violation_error_message="Este campo es obligatorio y no puede quedar vacío ni contener únicamente espacios."
            ),
            models.CheckConstraint(
                condition=~models.Q(fiscal_address="") & ~models.Q(fiscal_address__regex=r'^\s+$'),
                name="customer_fiscal_address_not_empty",
                violation_error_message="Este campo es obligatorio y no puede quedar vacío ni contener únicamente espacios."
            ),
            models.CheckConstraint(
                condition=~models.Q(phone_number="") & ~models.Q(phone_number__regex=r'^\s+$'),
                name="customer_phone_number_not_empty",
                violation_error_message="Este campo es obligatorio y no puede quedar vacío ni contener únicamente espacios."
            ),
            models.CheckConstraint(
                condition=~models.Q(taxpayer_type="") & ~models.Q(taxpayer_type__regex=r'^\s+$'),
                name="customer_taxpayer_type_not_empty",
                violation_error_message="Este campo es obligatorio y no puede quedar vacío ni contener únicamente espacios."
            )
        ]

    def clean(self) -> None:
        """Ejecuta validaciones de negocio complejas antes de guardar.

        Raises:
            ValidationError: Si se detectan inconsistencias tributarias.
        """
        super().clean()

        if self.rif and self.taxpayer_type:
            prefix = self.rif[0].upper()
            if prefix in ("V", "E") and self.taxpayer_type == self.TaxpayerType.SPECIAL:
                raise ValidationError({
                    "rif": (
                        "Inconsistencia tributaria: El prefijo del RIF "
                        "no corresponde con el Tipo de Contribuyente seleccionado."
                    )
                })

    def __str__(self) -> str:
        """Retorna una representación legible del modelo."""
        return f"{self.rif} - {self.name}"