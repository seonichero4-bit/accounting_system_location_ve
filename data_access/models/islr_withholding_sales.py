"""Módulo que define el modelo de datos para el comprobante de retención de ISLR.

Este modelo registra de forma inmutable la transacción de retención de Impuesto
Sobre la Renta, garantizando el aislamiento de datos (multi-tenant) a través 
de la clase abstracta base y validando rigurosamente los cálculos fiscales.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from data_access.models.base import FiscalModuleAbstractModel
from data_access.models.customer import Customer
from data_access.models.sales_record import SalesRecord


class IslrWithHolding(FiscalModuleAbstractModel):
    """Modelo para el Comprobante de Retención de ISLR.
    
    Hereda de FiscalModuleAbstractModel para incluir la relación obligatoria
    con el `fiscal_profile` (Tenant) e impone reglas contables y fiscales 
    venezolanas a nivel de base de datos y aplicación.
    """

    # Identificación y Control
    voucher_number = models.CharField(
        max_length=20,
        verbose_name="Voucher Number"
    )
    issue_date = models.DateField(
        verbose_name="Issue Date"
    )
    fiscal_period = models.DateField(
        verbose_name="Fiscal Period"
    )

    # Identificación del Agente de Retención / Cliente (Snapshot Histórico)
    client_name = models.CharField(
        max_length=250,
        verbose_name="Client Name"
    )
    client_rif = models.CharField(
        max_length=20,
        verbose_name="Client RIF"
    )

    # Datos del Documento de Origen y Operación (Snapshot Histórico)
    document_number = models.CharField(
        max_length=50,
        verbose_name="Document Number"
    )
    control_number = models.CharField(
        max_length=50,
        verbose_name="Control Number"
    )
    document_date = models.DateField(
        verbose_name="Document Date"
    )
    seniat_code = models.CharField(
        max_length=20,
        verbose_name="SENIAT Code"
    )

    # Desglose Financiero e Impositivo
    gross_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.01"),
                message="El monto ingresado no puede ser negativo. Debe ser un valor mayor o igual a 0.01."
            )
        ],
        verbose_name="Gross Amount"
    )
    tax_base = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.01"),
                message="El monto ingresado no puede ser negativo. Debe ser un valor mayor o igual a 0.01."
            )
        ],
        verbose_name="Tax Base"
    )
    retention_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("1.00"),
                message="El porcentaje de retención debe estar comprendido entre el 1.00%% y el 100.00%%."
            ),
            MaxValueValidator(
                Decimal("100.00"),
                message="El porcentaje de retención debe estar comprendido entre el 1.00%% y el 100.00%%."
            )
        ],
        verbose_name="Retention Percentage"
    )
    subtracting = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Subtracting"
    )
    total_withheld_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.01"),
                message="El monto ingresado no puede ser negativo. Debe ser un valor mayor o igual a 0.01."
            )
        ],
        verbose_name="Total Withheld Amount"
    )
    net_amount_to_pay = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.01"),
                message="El monto ingresado no puede ser negativo. Debe ser un valor mayor o igual a 0.01."
            )
        ],
        verbose_name="Net Amount To Pay"
    )

    # Relaciones Estructurales
    client = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="islr_withholdings",
        verbose_name="Client"
    )
    document = models.OneToOneField(
        SalesRecord,
        on_delete=models.PROTECT,
        related_name="islr_withholding",
        verbose_name="Document"
    )

    class Meta:
        """Configuración de metadatos y restricciones a nivel de base de datos."""

        verbose_name = "ISLR Withholding"
        verbose_name_plural = "ISLR Withholdings"

        constraints = [
            models.UniqueConstraint(
                fields=["fiscal_profile", "voucher_number", "client"],
                name="unique_comprobante_per_profile",
                violation_error_message="Ya existe un comprobante registrado con este número para el mismo cliente y perfil fiscal."
            ),
            models.CheckConstraint(
                condition=models.Q(tax_base__lte=models.F("gross_amount")),
                name="check_base_lte_bruto",
                violation_error_message="Violación de integridad: La base imponible sobrepasa el monto bruto registrado."
            ),
        ]

    def clean(self) -> None:
        """Centraliza la validación de integridad y lógica de negocio.
        
        Acumula y reporta múltiples errores a nivel de modelo para:
        - Validar que la base imponible no supere el monto bruto.
        - Verificar la precisión del cálculo de la retención del ISLR.
        - Comprobar que el neto a pagar cuadre perfectamente.
        """
        super().clean()
        errors_dict: dict[str, str] = {}

        # 1. Validación Base vs. Bruto
        if self.tax_base is not None and self.gross_amount is not None:
            if self.tax_base > self.gross_amount:
                errors_dict["tax_base"] = (
                    "La base imponible no puede exceder el monto bruto de la operación."
                )

        # 2. Verificación del Cálculo de ISLR
        if (self.tax_base is not None and self.retention_percentage is not None
                and self.subtracting is not None and self.total_withheld_amount is not None):
            
            expected_amount = (self.tax_base * (self.retention_percentage / Decimal("100.00"))) - self.subtracting
            
            # Tolerancia por redondeo estipulada de 0.01
            if abs(self.total_withheld_amount - expected_amount) > Decimal("0.01"):
                errors_dict["total_withheld_amount"] = (
                    "El monto total retenido no coincide con el cálculo del ISLR "
                    "según la base imponible, el porcentaje y el sustraendo aplicados."
                )

        # 3. Verificación del Neto a Pagar
        if (self.net_amount_to_pay is not None and self.gross_amount is not None 
                and self.total_withheld_amount is not None):
            
            expected_net = self.gross_amount - self.total_withheld_amount
            if self.net_amount_to_pay != expected_net:
                errors_dict["net_amount_to_pay"] = (
                    "El monto neto a pagar es incorrecto. Debe ser igual a la diferencia "
                    "entre el monto bruto y el monto total retenido."
                )

        if errors_dict:
            raise ValidationError(errors_dict)

    def __str__(self) -> str:
        """Representación legible del comprobante de retención."""
        return f"ISLR Withholding {self.voucher_number} - {self.client_name}"