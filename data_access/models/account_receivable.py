"""Módulo que define el modelo de Cuenta por Cobrar (AccountReceivable).

Implementa la estructura para el control de deudas comerciales de clientes,
con cálculo de saldos en memoria basados en documentos fiscales y retenciones.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum

from data_access.models.base import FiscalModuleAbstractModel


class AccountReceivableStatusChoices(models.TextChoices):
    """Estados del ciclo de vida de una cuenta por cobrar."""

    PENDING = 'PENDING', 'Pendiente'
    PARTIALLY_PAID = 'PARTIALLY_PAID', 'Abonada'
    PAID = 'PAID', 'Pagada / Extinguida'
    ANNULLED = 'ANNULLED', 'Anulada'


class AccountReceivable(FiscalModuleAbstractModel):
    """Modelo representativo para el control de Cuentas por Cobrar (CxC).

    Garantiza el cálculo en tiempo real del saldo neto exigible consolidando
    las ventas, retenciones aplicadas y pagos imputados, previniendo estados
    financieros inconsistentes.
    """

    sales_record = models.OneToOneField(
        'data_access.SalesRecord',
        on_delete=models.PROTECT,
        related_name='account_receivable',
        verbose_name="Sales Record"
    )
    fiscal_period = models.DateField(
        verbose_name="Fiscal Period"
    )
    status = models.CharField(
        max_length=20,
        choices=AccountReceivableStatusChoices.choices,
        default=AccountReceivableStatusChoices.PENDING,
        verbose_name="Status"
    )

    class Meta:
        """Configuración de metadatos del modelo AccountReceivable."""

        verbose_name = "Account Receivable"
        verbose_name_plural = "Accounts Receivable"
        constraints = [
            models.UniqueConstraint(
                fields=['sales_record', 'fiscal_profile'],
                name='unique_account_receivable_per_document_fiscal_profile',
                violation_error_message="Ya existe una cuenta por cobrar registrada para este documento de venta en el perfil fiscal activo."
            )
        ]

    @property
    def accumulated_net_retention(self) -> Decimal:
        """Retorna la consolidación algebraica de retenciones fiscales.

        Suma los montos de IVA e ISLR retenidos asociados a la factura origen y 
        ejecuta la consolidación aritmética si existen notas de crédito (restan) 
        o notas de débito (suman) que posean retenciones vinculadas.

        Returns:
            Decimal: El monto total acumulado retenido neto.
        """
        # Importaciones locales para evitar dependencias circulares
        from data_access.models.vat_withholding_sales import VatWithHolding
        from data_access.models.islr_withholding_sales import IslrWithHolding
        from data_access.models.sales_record import SalesRecord
        from django.db.models import Sum

        def get_total_retentions(documents) -> Decimal:
            """Calcula la suma total de IVA e ISLR para un conjunto de documentos."""
            vat_total = VatWithHolding.objects.filter(
                document__in=documents
            ).aggregate(total=Sum('withheld_amount'))['total'] or Decimal('0.00')

            islr_total = IslrWithHolding.objects.filter(
                document__in=documents
            ).aggregate(total=Sum('total_withheld_amount'))['total'] or Decimal('0.00')

            return vat_total + islr_total

        # 1. Retención originaria (SalesRecord principal)
        base_retention = get_total_retentions([self.sales_record])

        # 2. Buscar Notas de Crédito asociadas (Restan a la retención originaria)
        credit_notes = SalesRecord.objects.filter(
            affected_invoice=self.sales_record,
            document_type=SalesRecord.DocumentType.CREDIT_NOTE
        )
        credit_retention = get_total_retentions(credit_notes)

        # 3. Buscar Notas de Débito asociadas (Suman a la retención originaria)
        debit_notes = SalesRecord.objects.filter(
            affected_invoice=self.sales_record,
            document_type=SalesRecord.DocumentType.DEBIT_NOTE
        )
        debit_retention = get_total_retentions(debit_notes)

        # 4. Consolidación algebraica final
        return base_retention + debit_retention - credit_retention

    @property
    def net_receivable_balance(self) -> Decimal:
        """Calcula en tiempo real el saldo exigible de la obligación comercial.

        Ecuación: total de venta - retenciones acumuladas - pagos imputados.

        Returns:
            Decimal: El balance neto por cobrar actual.
        """
        total_sales = self.sales_record.total_sales_inc_vat or Decimal('0.00')
        retentions = self.accumulated_net_retention

        imputations_total = self.imputations.aggregate(
            total=Sum('imputed_amount')
        )['total'] or Decimal('0.00')

        return total_sales - retentions - imputations_total

    def clean(self) -> None:
        """Valida y restringe las transiciones de estado permitidas."""
        super().clean()
        errors: dict[str, str] = {}

        if self.status == AccountReceivableStatusChoices.PAID:
            if self.net_receivable_balance > Decimal('0.00'):
                errors['status'] = "No se puede marcar la cuenta por cobrar como pagada porque aún posee un saldo neto exigible pendiente."

        if self.status == AccountReceivableStatusChoices.ANNULLED:
            errors['status'] = "No se pueden realizar operaciones sobre una cuenta por cobrar que se encuentra anulada."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        """Retorna una representación legible de la Cuenta por Cobrar."""
        return f"CxC - Documento: {self.sales_record_id} - Estado: {self.status}"