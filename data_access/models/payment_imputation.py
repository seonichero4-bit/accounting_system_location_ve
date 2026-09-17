"""Módulo que define la Imputación de Pagos (PaymentImputation).

Interconecta un pago en Tesorería con la Cuenta por Cobrar pertinente,
aplicando topes financieros rigurosos.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from data_access.models.base import FiscalModuleAbstractModel


class PaymentImputation(FiscalModuleAbstractModel):
    """Modelo para la asignación y cruce de cobros contra CxC.

    Representa la fracción individual de un CustomerPayment destinada
    a amortizar una obligación comercial específica.
    """

    payment = models.ForeignKey(
        'data_access.CustomerPayment',
        on_delete=models.CASCADE,
        related_name='imputations',
        verbose_name="Payment"
    )
    account_receivable = models.ForeignKey(
        'data_access.AccountReceivable',
        on_delete=models.PROTECT,
        related_name='imputations',
        verbose_name="Account Receivable"
    )
    fiscal_period = models.DateField(
        verbose_name="Fiscal Period"
    )
    imputed_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal('0.01'),
                message="El monto a imputar debe ser un valor positivo mayor a cero."
            )
        ],
        verbose_name="Imputed Amount"
    )

    class Meta:
        """Configuración de reglas de unicidad e índices."""

        verbose_name = "Payment Imputation"
        verbose_name_plural = "Payment Imputations"
        constraints = [
            models.UniqueConstraint(
                fields=['payment', 'account_receivable'],
                name='unique_imputation_per_payment_and_receivable',
                violation_error_message="No se puede imputar más de una vez el mismo pago a la misma cuenta por cobrar."
            )
        ]

    def clean(self) -> None:
        """Vela por el 'Tope Impugnable' evitando sobre-imputaciones."""
        super().clean()
        errors: dict[str, str] = {}

        if hasattr(self, 'account_receivable') and self.account_receivable and self.imputed_amount is not None:
            balance = self.account_receivable.net_receivable_balance

            # Si es una edición, se restaura temporalmente el monto original 
            # al saldo vivo antes de validar el nuevo ingreso para no sobre-bloquearlo.
            if self.pk:
                original = self.__class__.objects.filter(pk=self.pk).first()
                if original:
                    balance += original.imputed_amount

            if self.imputed_amount > balance:
                errors['imputed_amount'] = f"El monto a imputar excede el saldo neto exigible vigente ({balance}) de la cuenta por cobrar seleccionada."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        """Retorna una representación legible del monto imputado."""
        return f"Imputación: {self.imputed_amount} (CxC: {self.account_receivable_id})"