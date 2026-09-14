"""Módulo que define el modelo de comprobante de retención de IVA.

Asegura el registro inmutable de la retención bajo una arquitectura multi-tenant,
validando las restricciones fiscales requeridas (porcentajes legales, cronología,
unicidad y estatus del documento de venta asociado).
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

from data_access.models.base import FiscalModuleAbstractModel


class VatWithHolding(FiscalModuleAbstractModel):
    """Modelo que representa un comprobante de retención de IVA.
    
    Hereda de FiscalModuleAbstractModel para garantizar el aislamiento de datos
    por inquilino (tenant) mediante la relación con FiscalProfile. Registra
    una fotografía exacta (snapshot) de los datos al momento de la retención.
    """

    voucher_number = models.CharField(
        max_length=14,
        validators=[
            RegexValidator(
                regex=r'^\d{14}$',
                message="El número de comprobante debe contener exactamente 14 dígitos numéricos (ejemplo: 20260500000001). Por favor, verifique el número ingresado."
            )
        ],
        verbose_name="Voucher Number"
    )
    issue_date = models.DateField(
        verbose_name="Issue Date"
    )
    fiscal_period = models.DateField(
        verbose_name="Fiscal Period"
    )

    client_name = models.CharField(
        max_length=250,
        verbose_name="Client Name"
    )
    client_rif = models.CharField(
        max_length=20,
        verbose_name="Client RIF"
    )

    document_number = models.CharField(
        max_length=50,
        verbose_name="Document Number"
    )
    control_number = models.CharField(
        max_length=50,
        verbose_name="Control Number"
    )

    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Total Amount"
    )
    tax_base = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Tax Base"
    )
    tax_caused = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Tax Caused"
    )
    withheld_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal('0.00'),
                message="El monto retenido no puede ser negativo. Por favor, ingrese un valor igual o mayor a cero."
            )
        ],
        verbose_name="Withheld Amount"
    )

    client = models.ForeignKey(
        "data_access.Customer",
        on_delete=models.PROTECT,
        related_name="vat_withholdings",
        verbose_name="Client"
    )
    document = models.OneToOneField(
        "data_access.SalesRecord",
        on_delete=models.PROTECT,
        related_name="vat_withholding",
        verbose_name="Source Document"
    )

    class Meta:
        """Configuración de metadatos del modelo VatWithHolding."""
        
        verbose_name = "VAT Withholding"
        verbose_name_plural = "VAT Withholdings"
        constraints = [
            models.UniqueConstraint(
                fields=["voucher_number", "client", "fiscal_profile"],
                name="%(app_label)s_%(class)s_unique_voucher_per_client_tenant",
                violation_error_message="Ya existe un comprobante registrado con este número consecutivo para el cliente y perfil fiscal seleccionado. Introduzca un número distinto."
            ),
            models.CheckConstraint(
                condition=models.Q(withheld_amount__gte=Decimal('0.00')),
                name="%(app_label)s_%(class)s_positive_withheld_amount",
                violation_error_message="El monto retenido debe ser mayor o igual a cero."
            )
        ]

    def clean(self) -> None:
        """Centraliza las validaciones de negocio e integridad del comprobante.
        
        Raises:
            ValidationError: Si alguna restricción de lógica de negocio o
            consistencia cronológica es violada.
        """
        super().clean()
        errors_dict: dict[str, str] = {}

        # 1. Validación de Estatus del Documento de Origen y 3. Precedencia Cronológica
        if hasattr(self, 'document') and self.document_id:
            # Compatibilidad dinámica con las opciones del modelo SalesRecord (RecordStatus)
            invalid_statuses = ["ANNULLED", "PROCESSED", "ANNULLED_PROCESSED"]
            status_values = [
                getattr(self.document.RecordStatus, status, status) for status in invalid_statuses 
                if hasattr(self.document, "RecordStatus")
            ] or invalid_statuses

            if self.document.record_status in status_values:
                errors_dict["__all__"] = "No es posible emitir ni asociar un comprobante de retención a esta factura porque se encuentra anulada o procesada. Solo se permite retener sobre facturas activas."

            if self.issue_date and self.document.document_date:
                if self.issue_date < self.document.document_date:
                    errors_dict["issue_date"] = "La fecha de emisión del comprobante no puede ser anterior a la fecha de la factura de venta asociada. Verifique las fechas ingresadas."

        # 2. Prohibición de Fechas Futuras
        if self.issue_date:
            if self.issue_date > timezone.now().date():
                errors_dict["issue_date"] = "La fecha de emisión del comprobante no puede ser posterior a la fecha actual. Por favor, seleccione una fecha válida."

        # 4. Coherencia Cronológica del Secuencial (AAAAMM)
        if self.issue_date and self.voucher_number:
            expected_prefix = self.issue_date.strftime("%Y%m")
            clean_voucher = self.voucher_number.strip()
            if not clean_voucher.startswith(expected_prefix):
                errors_dict["voucher_number"] = "El período (año y mes) del número de comprobante no coincide con su fecha de emisión. Para un comprobante emitido en MM/AAAA, los primeros 6 dígitos deben ser 'AAAAMM'."

        # 5. y 6. Correspondencia del Porcentaje (75% / 100%) y Techo Fiscal
        if self.withheld_amount is not None and self.tax_caused is not None:
            if self.withheld_amount > self.tax_caused:
                errors_dict["withheld_amount"] = "El monto retenido no puede ser mayor al impuesto causado (débito fiscal) total de la factura de venta."
            else:
                expected_75 = (self.tax_caused * Decimal("0.75")).quantize(Decimal("0.01"))
                expected_100 = (self.tax_caused * Decimal("1.00")).quantize(Decimal("0.01"))
                
                if self.withheld_amount not in [expected_75, expected_100]:
                    errors_dict["withheld_amount"] = "El monto retenido no coincide con el cálculo del porcentaje legal aplicable (75% o 100% del débito fiscal de la factura). Por favor, revise los importes ingresados."

        if errors_dict:
            raise ValidationError(errors_dict)
     
    def __str__(self) -> str:
        """Retorna una representación legible del comprobante de retención."""
        return f"Comprobante {self.voucher_number} - {self.client_name}"