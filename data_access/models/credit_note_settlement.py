"""Módulo para la liquidación de Notas de Crédito.

Implementa el modelo CreditNoteSettlement para registrar el desglose
operativo y financiero correspondiente a una Nota de Crédito fiscal.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from data_access.models.base import FiscalModuleAbstractModel


class CreditNoteSettlement(FiscalModuleAbstractModel):
    """Modelo para la Liquidación y Ajuste de Notas de Crédito.

    Actúa como una capa informativa y de auditoría aislada que vincula
    el documento fiscal con sus implicaciones operativas sin alterar
    automáticamente balances contables o de tesorería.
    """

    class SettlementType(models.TextChoices):
        """Opciones para la categorización del tipo de liquidación."""

        RETURNS = "RETURNS", "Devoluciones"
        DISCOUNTS = "DISCOUNTS", "Descuentos"
        MIXED = "MIXED", "Mixto"

    # --- Relación Principal ---
    sales_record = models.OneToOneField(
        "data_access.SalesRecord",
        on_delete=models.CASCADE,
        related_name="settlement",
        verbose_name="Registro de Venta Afectado",
    )

    # --- Categorización de Operación ---
    settlement_type = models.CharField(
        max_length=20,
        choices=SettlementType.choices,
        db_index=True,
        verbose_name="Tipo de Liquidación",
    )

    # --- Atributos de Desglose Operativo (Conceptos) ---
    returned_goods_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Valor de Bienes Devueltos",
    )
    reimbursement_in_services = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Reembolso/Cancelación en Servicios",
    )
    commercial_discount_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Monto de Descuento Comercial",
    )

    # --- Atributos de Reembolso Financiero (Canales Monetarios) ---
    bank_transfer_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Monto Transferencia Bancaria",
    )
    mobile_payment_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Monto Pago Móvil",
    )
    cash_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Monto Efectivo",
    )
    card_pos_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Monto Punto de Venta / Tarjeta",
    )
    customer_credit_balance_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Monto Reconocido como Saldo a Favor",
    )
    refunded_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name="Total Monto Desembolsado/Reembolsado",
    )

    # --- Soporte y Auditoría ---
    payment_reference = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Referencia de Pago",
    )
    fiscal_period = models.DateField(
        null=True,
        blank=True,
        verbose_name="Período Fiscal",
    )

    class Meta:
        """Configuración de metadatos del modelo CreditNoteSettlement."""

        verbose_name = "Liquidación de Nota de Crédito"
        verbose_name_plural = "Liquidaciones de Notas de Crédito"

        constraints = [
            models.CheckConstraint(
                condition=models.Q(returned_goods_value__gte=Decimal("0.00"))
                & models.Q(reimbursement_in_services__gte=Decimal("0.00"))
                & models.Q(commercial_discount_amount__gte=Decimal("0.00"))
                & models.Q(bank_transfer_amount__gte=Decimal("0.00"))
                & models.Q(mobile_payment_amount__gte=Decimal("0.00"))
                & models.Q(cash_amount__gte=Decimal("0.00"))
                & models.Q(card_pos_amount__gte=Decimal("0.00"))
                & models.Q(customer_credit_balance_amount__gte=Decimal("0.00"))
                & models.Q(refunded_amount__gte=Decimal("0.00")),
                name="non_negative_settlement_amounts",
            ),
            models.UniqueConstraint(
                fields=["fiscal_profile", "sales_record"],
                name="unique_settlement_per_sales_record",
            ),
        ]

    def clean(self) -> None:
        """Sanea y valida las reglas de negocio e integridad financiera estricta.

        Raises:
            ValidationError: Si se detecta un cuadre fallido o violación a las reglas
                especificadas para el tipo de liquidación.
        """
        super().clean()
        errors: dict[str, str] = {}

        # Validación 0: Evitar excepciones de ORM por OneToOne nulo antes de evaluar
        if not getattr(self, "sales_record_id", None):
            raise ValidationError(
                {"sales_record": "El registro de venta afectado es obligatorio."}
            )

        try:
            sales_record = self.sales_record
        except Exception:
            raise ValidationError(
                {"sales_record": "El registro de venta afectado es obligatorio."}
            )

        # 1. Restricción de Tipo Documental Permitido
        doc_type = getattr(sales_record, "document_type", "")
        if doc_type != "CREDIT_NOTE":
            errors["sales_record"] = (
                "Solo se pueden asociar liquidaciones a registros cuyo tipo de "
                "documento sea Nota de Crédito ('CREDIT_NOTE')."
            )

        # Preparación de variables de cálculo (manejo seguro para valores en memoria)
        rgv = self.returned_goods_value or Decimal("0.00")
        ris = self.reimbursement_in_services or Decimal("0.00")
        cda = self.commercial_discount_amount or Decimal("0.00")

        bta = self.bank_transfer_amount or Decimal("0.00")
        mpa = self.mobile_payment_amount or Decimal("0.00")
        ca = self.cash_amount or Decimal("0.00")
        cpa = self.card_pos_amount or Decimal("0.00")
        ccba = self.customer_credit_balance_amount or Decimal("0.00")
        ra = self.refunded_amount or Decimal("0.00")

        # 2. Ecuación de Cuadre del Desglose Operativo
        total_operative = rgv + ris + cda
        total_sales = getattr(sales_record, "total_sales_inc_vat", Decimal("0.00")) or Decimal("0.00")

        if total_operative != total_sales:
            errors["__all__"] = (
                "La suma del desglose operativo (bienes, servicios y descuento comercial) "
                "no coincide con el monto total de la Nota de Crédito."
            )

        # 3. Ecuación de Cuadre del Reembolso Financiero
        total_financial = bta + mpa + ca + cpa + ccba
        if total_financial != ra:
            errors["refunded_amount"] = (
                "El monto total reembolsado no coincide con la sumatoria de las "
                "vías monetarias especificadas."
            )

        # 4. Reglas Específicas por Tipo de Liquidación (settlement_type)
        st = self.settlement_type
        if st == self.SettlementType.RETURNS:
            if cda > Decimal("0.00"):
                errors["commercial_discount_amount"] = (
                    "Para liquidaciones de tipo 'Devoluciones', el descuento comercial "
                    "debe ser estrictamente 0.00."
                )
        elif st == self.SettlementType.DISCOUNTS:
            if rgv > Decimal("0.00") or ris > Decimal("0.00"):
                errors["settlement_type"] = (
                    "Para liquidaciones de tipo 'Descuentos', los valores de bienes y "
                    "servicios devueltos deben ser estrictamente 0.00."
                )
            if ra > Decimal("0.00"):
                errors["refunded_amount"] = (
                    "Para liquidaciones de tipo 'Descuentos', no se permiten desembolsos "
                    "o reembolsos dinerarios."
                )
        elif st == self.SettlementType.MIXED:
            has_returns = rgv > Decimal("0.00") or ris > Decimal("0.00")
            has_discount = cda > Decimal("0.00")
            if not (has_returns and has_discount):
                errors["settlement_type"] = (
                    "Para liquidaciones de tipo 'Mixto', se requiere la presencia simultánea "
                    "de conceptos de devolución y de descuento comercial."
                )
            if ra > (rgv + ris):
                errors["refunded_amount"] = (
                    "El monto desembolsado no puede ser superior al valor asignado a la "
                    "devolución de bienes y servicios."
                )

        # 5. Coherencia con la Categoría de Venta Fiscal (Sale Category)
        sale_cat = getattr(sales_record, "sale_category", "")
        if sale_cat == "SERVICES":
            if rgv > Decimal("0.00"):
                errors["returned_goods_value"] = (
                    "No se puede asignar valor a bienes devueltos cuando la venta "
                    "original es exclusivamente de categoría 'Servicios'."
                )
        elif sale_cat == "GOODS":
            if ris > Decimal("0.00"):
                errors["reimbursement_in_services"] = (
                    "No se puede asignar reembolso en servicios cuando la venta "
                    "original es exclusivamente de categoría 'Bienes'."
                )

        # 6. Requisito de Referencia de Pago
        if bta > Decimal("0.00") or mpa > Decimal("0.00"):
            if not self.payment_reference or not self.payment_reference.strip():
                errors["payment_reference"] = (
                    "La referencia de pago es obligatoria cuando existen desembolsos "
                    "vía transferencia bancaria o pago móvil."
                )

        if errors:
            raise ValidationError(errors)