"""Módulo que define el modelo de Cobro (CustomerPayment) para tesorería.

Registra las transacciones y pagos financieros de los clientes, garantizando
la integridad de las tasas de cambio y el cuadre lógico.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from data_access.models.base import FiscalModuleAbstractModel


class CurrencyChoices(models.TextChoices):
    """Opciones de monedas permitidas en transacciones financieras."""

    VES = 'VES', 'Bolívares'
    USD = 'USD', 'Dólares'
    EUR = 'EUR', 'Euros'


class PaymentMethodTypeChoices(models.TextChoices):
    """Catálogo de métodos de pago soportados."""

    BANK_TRANSFER = 'BANK_TRANSFER', 'Transferencia Bancaria'
    MOBILE_PAYMENT = 'MOBILE_PAYMENT', 'Pago Móvil'
    CASH = 'CASH', 'Efectivo'
    POS = 'POS', 'Punto de Venta'


class CustomerPayment(FiscalModuleAbstractModel):
    """Modelo para registrar ingresos consolidados en tesorería.

    Abarca información del método de pago, divisa empleada y tasa aplicable,
    verificando el cuadre exacto con las imputaciones sobre las CxC.
    """

    customer = models.ForeignKey(
        'data_access.Customer',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name="Customer"
    )
    fiscal_period = models.DateField(
        verbose_name="Fiscal Period"
    )
    payment_date = models.DateField(
        verbose_name="Payment Date"
    )
    method_type = models.CharField(
        max_length=20,
        choices=PaymentMethodTypeChoices.choices,
        verbose_name="Payment Method"
    )
    currency = models.CharField(
        max_length=10,
        choices=CurrencyChoices.choices,
        verbose_name="Currency"
    )
    nominal_value = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.01'),
        validators=[
            MinValueValidator(
                Decimal('0.01'),
                message="El valor nominal debe ser mayor a cero."
            )
        ],
        verbose_name="Nominal Value"
    )
    exchange_rate = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        default=Decimal('1.0000'),
        verbose_name="Exchange Rate"
    )
    total_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Total Amount"
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Reference"
    )

    class Meta:
        """Configuración de metadatos del modelo CustomerPayment."""

        verbose_name = "Customer Payment"
        verbose_name_plural = "Customer Payments"

    def clean(self) -> None:
        """Valida la coherencia temporal, contable y el cuadre global del pago."""
        super().clean()
        errors: dict[str, str] = {}

        if self.total_amount is not None and self.total_amount <= Decimal('0.00'):
            errors['total_amount'] = "El monto total del pago debe ser mayor a cero."

        # Captura el total de imputaciones; previene ValueError si se evalúa
        # un objeto en memoria que no cuenta con PK aún y no tiene iterables viables.
        try:
            imputations_total = sum(imp.imputed_amount for imp in self.imputations.all())
        except ValueError:
            imputations_total = Decimal('0.00')

        if self.total_amount is not None and imputations_total != self.total_amount:
            if 'total_amount' not in errors:
                errors['total_amount'] = "El monto total reportado en el pago no coincide con la sumatoria de los montos imputados a las cuentas por cobrar."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        """Retorna una representación legible de la transacción."""
        return f"Pago {self.pk} - {self.customer} - {self.total_amount} {self.currency}"