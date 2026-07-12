"""Módulo de persistencia para comprobantes de retención fiscal.

Define los modelos legales localizados para gestionar las retenciones preventivas
de IVA (Impuesto al Valor Agregado) e ISLR (Impuesto Sobre la Renta) vinculadas
al libro de compras multi-inquilino.
"""

from decimal import Decimal
from typing import Any
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

#from data_access.mixins.sequence import TransactionalSequenceMixin
from data_access.models.base import FiscalModuleAbstractModel
from data_access.models.purchase_book import PurchaseLedgerInvoice#, PurchaseInvoiceLine


class VatWithholdingCertificate(FiscalModuleAbstractModel):
    """Modelo legal para el registro de comprobantes de retención de IVA.

    Establece un vínculo unívoco e inseparable con una factura de compra del libro
    fiscal, resguardando la integridad de la recaudación del tributo. Genera de
    manera automática un número de documento transaccional periódico.
    """

    class  VatWithholdingPercentage(models.DecimalField):
        """Opciones de porcentaje de IVA según la legislación venezolana."""
        
        SETENTA_Y_CINCO = 75, "75 %"
        CIEN = 100, "100 %"
        
    class CertificateStatus(models.TextChoices):
        """Estados operativos y fiscales de la factura."""

        PRELIMINARY = "PRELIMINARY", "Preliminary"
        PROCESSED = "PROCESSED", "Processed"

    # Configuración de propiedades para el TransactionalSequenceMixin
    #PREFIX = "RETENCION_IVA"
    #PADDING_LENGTH = 5

    purchase_invoice = models.OneToOneField(
        PurchaseLedgerInvoice,
        on_delete=models.PROTECT,
        related_name="vat_withholding_certificate",
        verbose_name="Associated Purchase Invoice",
    )
    application_date = models.DateField(
        verbose_name="Fiscal Application Date",
    )
    vat_withholding_percentage = models.DecimalField(
        choices=VatWithholdingPercentage.choices,
        default=VatWithholdingPercentage.SETENTA_Y_CINCO,
        max_digits=5,
        decimal_places=2,
        verbose_name="VAT Withholding Percentage (%)",
    )
    document_number = models.CharField(
        max_length=50,
        blank=True,
        editable=False,
        verbose_name="Withholding Document Number",
    )
    vat_withheld_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="VAT Withheld Amount",
    )
     # Control de Flujo del Ciclo de Vida
    status = models.CharField(
        max_length=15,
        choices=CertificateStatus.choices,
        default=CertificateStatus.PRELIMINARY,
        verbose_name="Invoice Status",
    )
    

    class Meta:
        """Configuración de metadatos del modelo ComprobanteRetencionIVA."""

        verbose_name = "VAT Withholding Certificate"
        verbose_name_plural = "VAT Withholding Certificates"
        constraints = [
            models.UniqueConstraint(
                fields=["fiscal_profile", "document_number",],
                name="unique_withholding_per_fiscal_profile",
            ),
            models.CheckConstraint(
                condition=models.Q(application_date__lte=models.functions.Now()),
                name="withholding_date_not_future",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    vat_withholding_percentage__in=[
                        Decimal("75.00"),
                        Decimal("100.00"),
                    ]
                ),
                name="valid_withholding_percentages",
            ),
        ]

    def __str__(self) -> str:
        """Retorna una representación legible del comprobante de IVA."""
        return f"VAT Certificate No. {self.document_number}"

    def clean(self) -> None:
        """Valida las reglas de negocio cruzadas del comprobante de retención.

        Lanza ValidationError si no se cumplen los criterios fiscales para
        la factura asociada, fechas o el formato del número de documento.
        """
        super().clean()
        errors: dict[str, str] = {}

        # 1. Validación de purchase_invoice
        if hasattr(self, "purchase_invoice") and self.purchase_invoice:
            # Validación de estado de la factura (Procesado, Registrado o Posted)
            invoice_status = getattr(self.purchase_invoice, "status", None)
            if invoice_status is not "PRELIMINARY":
                errors["purchase_invoice"] = (
                    "La factura asociada ya fue procesada."
                )

        # Validación de monto de IVA mayor a cero
            vat_amount = getattr(self.purchase_invoice, "vat_amount", Decimal("0.00"))
            if vat_amount <= Decimal("0.00"):
                errors["purchase_invoice"] = (
                    "El IVA de la factura asociada debe ser estrictamente mayor a cero."
                )

            # 2. Validación de application_date vs fecha de emisión de la factura de compra
            invoice_date = getattr(self.purchase_invoice, "date", None)
            if invoice_date and self.application_date < invoice_date:
                errors["application_date"] = (
                    "La fecha de aplicación no puede ser menor a la fecha de emisión de la factura asociada."
                )

        # Validación de período fiscal activo controlado por el sistema
        if self.application_month_year and hasattr(self, "fiscal_profile") and self.fiscal_profile:
            if hasattr(self.fiscal_profile, "is_period_active") and not self.fiscal_profile.is_period_active(
                self.application_month_year
            ):
                errors["application_month_year"] = (
                    "La fecha seleccionada no pertenece a un período fiscal activo en el sistema."
                )

        # 3. Validación de consistencia de document_number con application_date (YYYYMM)
        if self.document_number and self.application_month_year:
            expected_prefix = self.application_month_year.strftime("%Y%m")
            if self.document_number[:6] != expected_prefix:
                errors["document_number"] = (
                    f"Inconsistencia fiscal: Los primeros 6 caracteres del número de comprobante "
                    f"deben coincidir exactamente con el año y mes de la fecha de aplicación ({expected_prefix})."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Calcula de forma automática los montos e implementa inmutabilidad si está procesado.

        Lanza un ValidationError si se intenta modificar un registro cuyo estado
        en la base de datos ya era PROCESSED.
        """
        if self.pk is not None:
            original = VatWithholdingCertificate.objects.get(pk=self.pk)
            if original.status == self.CertificateStatus.PROCESSED:
                raise ValidationError(
                    "Este comprobante de retención ya ha sido procesado y es estrictamente de solo lectura."
                )

        # Cálculo automático del monto retenido resguardando tipos Decimal
        if self.status != self.CertificateStatus.PROCESSED or self.pk is None:
            vat_amount = Decimal(str(self.purchase_invoice.vat_amount))
            percentage = Decimal(str(self.vat_withholding_percentage))
            self.vat_withheld_amount = round(vat_amount * (percentage / Decimal("100.00")), 2)

        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        """Bloquea la eliminación física de registros históricos procesados.

        Lanza un ValidationError si el estado actual es PROCESSED.
        """
        if self.status == self.CertificateStatus.PROCESSED:
            raise ValidationError(
                "Los comprobantes emitidos y procesados no pueden ser eliminados del sistema por razones legales."
            )
        return super().delete(*args, **kwargs)
    


    # def save(self, *args: Any, **kwargs: Any) -> None:
    #     """Persiste el comprobante ejecutando la pre-generación del número de documento."""
    #     self.handle_transactional_code()
    #     super().save(*args, **kwargs)


