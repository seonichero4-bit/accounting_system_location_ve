import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Tuple
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from data_access.models.base import FiscalModuleAbstractModel
from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.concep_payment_islr.concepts_payment_pjd import IslrPjdChoices
from data_access.models.concep_payment_islr.concepts_payment_pjnd import IslrPjndChoices
from data_access.models.concep_payment_islr.concepts_payment_pnnr import IslrPnnrChoices
from data_access.models.concep_payment_islr.concepts_payment_pnr import IslrPnrChoices
from business_logic.services.ut_setup import TAX_UNIT as ut_value



class IslrWithholdingCertificate(FiscalModuleAbstractModel):
    """Modelo de control para comprobantes de retención de ISLR.

    Asocia las retenciones del Impuesto Sobre la Renta ejecutadas sobre conceptos y
    líneas operativas específicas desglosadas en las compras del período. Genera de
    manera automática un número de documento transaccional periódico.
    """
    class CertificateStatus(models.TextChoices):
        """Estados operativos y fiscales de la factura."""

        PRELIMINARY = "PRELIMINARY", "Preliminary"
        PROCESSED = "PROCESSED", "Processed"

    purchase_invoice = models.OneToOneField(
        PurchaseLedgerInvoice,
        on_delete=models.PROTECT,
        related_name="islr_withholding_certificates",
        verbose_name="Related Purchase Invoice",
    )
    document_number = models.CharField(
        max_length=50,
        verbose_name="ISLR Document Number",
    )
    application_date = models.DateField(
        verbose_name="Fiscal Application Date",
    )
    fiscal_period = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fiscal Period(DD-MM-YYYY)",
    )
    islr_withheld_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="ISLR Withheld Amount",
    )
    subtracting = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Amount of the applied subtrahend",
    )
    # Control de Flujo del Ciclo de Vida
    status = models.CharField(
        max_length=15,
        choices=CertificateStatus.choices,
        default=CertificateStatus.PRELIMINARY,
        verbose_name="Invoice Status",
    )

    # =========================================================================
    # CAMPOS CHOICE PARA CONCEPTOS DE RETENCIÓN DE ISLR
    # =========================================================================

    concepts_payment_pnnr = models.PositiveSmallIntegerField(
        choices=IslrPnnrChoices.choices,
        blank=True,
        null=True,
        verbose_name="Concepto de Pago - Persona Natural No Residente (PNNR)",
        help_text="Concepto de retención aplicable a personas naturales no residentes.",
    )
    concepts_payment_pnr = models.PositiveSmallIntegerField(
        choices=IslrPnrChoices.choices,
        blank=True,
        null=True,
        verbose_name="Concepto de Pago - Persona Natural Residente (PNR)",
        help_text="Concepto de retención aplicable a personas naturales residentes.",
    )
    concepts_payment_pjnd = models.PositiveSmallIntegerField(
        choices=IslrPjndChoices.choices,  # Mapeado a No Domiciliadas
        blank=True,
        null=True,
        verbose_name="Concepto de Pago - Persona Jurídica No Residente (PJNR)",
        help_text="Concepto de retención aplicable a personas jurídicas no domiciliadas.",
    )
    concepts_payment_pjd = models.PositiveSmallIntegerField(
        choices=IslrPjdChoices.choices,   # Mapeado a Domiciliadas
        blank=True,
        null=True,
        verbose_name="Concepto de Pago - Persona Jurídica Residente (PJR)",
        help_text="Concepto de retención aplicable a personas jurídicas domiciliadas.",
    )

    # =========================================================================
    # Metodos para el calculo de "islr_withheld_amount" y ""
    # =========================================================================

    def calculate_pnnr_withholding(self) -> None:
        """
        Calcula de forma automática el monto de retención de ISLR para Personas Naturales No Residentes (PNNR).

        Aplica el modelo matemático multiplicando el subtotal de la factura de compra asociada 
        por el factor de la base imponible y la alícuota de retención correspondientes al concepto 
        configurado. El resultado final se redondea de forma simétrica a dos decimales (ROUND_HALF_UP) 
        y se asigna al atributo 'islr_withheld_amount'.
        """

        # Extracción de variables financieras basándose en el marco legal del enumerador
        concept_choice = IslrPnnrChoices(self.concepts_payment_pnnr)
        subtotal: Decimal = getattr(self.purchase_invoice, "subtotal", Decimal("0.00"))
        factor_base: Decimal = concept_choice.base_imponible
        alicuota: Decimal = concept_choice.percentage

        # Aplicación de la ecuación fiscal
        calculated_amount: Decimal = subtotal * factor_base * alicuota

        # Redondeo financiero estricto a dos (2) decimales (0.01) para el SENIAT
        self.islr_withheld_amount = calculated_amount.quantize(
            Decimal("0.01"), 
            rounding=ROUND_HALF_UP
        )

    def calculate_pnr_withholding(self) -> None:
        """
        Calcula y asigna simultáneamente la retención neta de ISLR y el sustraendo legal
        para Personas Naturales Residentes (PNR) bajo la normativa del SENIAT.

        Sigue estrictamente los flujos de control basados en el umbral mínimo de
        Unidades Tributarias (fixed_factor) y el derecho de deducción (application_subtrahend),
        mutando en memoria los atributos 'subtracting' e 'islr_withheld_amount'.
        """

        invoice = self.purchase_invoice
        fiscal_profile = getattr(invoice, "fiscal_profile", None)
        if not fiscal_profile:
            raise ValidationError(
                "La factura de compra asociada no posee un perfil fiscal (fiscal_profile) válido.",
                code="missing_fiscal_profile"
            )
        # Variables de entrada base
        concept_choice = IslrPnrChoices(self.concepts_payment_pnr)
        subtotal: Decimal = getattr(invoice, "subtotal", Decimal("0.00"))
        ut: Decimal = Decimal(str(ut_value))

        # Propiedades del concepto normativo
        base_imponible: Decimal = concept_choice.base_imponible
        percentage: Decimal = concept_choice.percentage
        applies_subtrahend: bool = concept_choice.application_subtrahend
        fixed_factor: Decimal = concept_choice.fixed_factor

        # Inicialización de acumuladores crudos
        raw_subtracting = Decimal("0.00")
        raw_withheld_amount = Decimal("0.00")

        if applies_subtrahend:
            # ESCENARIO A: Conceptos con Sustraendo Activo
            base_ut = subtotal / ut

            if base_ut >= fixed_factor:
                # Verificación de Umbral Mínimo Superada: Beneficio fiscal completo
                raw_subtracting = fixed_factor * ut * percentage
                raw_withheld_amount = (subtotal * base_imponible * percentage) - raw_subtracting
            else:
                # Menor al umbral mínimo exigido por ley: No califica para retención
                raw_subtracting = Decimal("0.00")
                raw_withheld_amount = Decimal("0.00")
        else:
            # ESCENARIO B: Conceptos sin Sustraendo
            raw_subtracting = Decimal("0.00")
            raw_withheld_amount = subtotal * base_imponible * percentage

        # Política de Redondeo Financiero Estricto (ROUND_HALF_UP) a dos (2) posiciones decimales
        precision = Decimal("0.01")
        self.subtracting = raw_subtracting.quantize(precision, rounding=ROUND_HALF_UP)
        self.islr_withheld_amount = raw_withheld_amount.quantize(precision, rounding=ROUND_HALF_UP)

    def calculate_pjnd_withholding(self) -> None:
        """
        Calcula y asigna el impuesto neto retenido (islr_withheld_amount) para 
        Personas Jurídicas No Domiciliadas (PJND) evaluando el Flujo Ordinario 
        o la escala progresiva de la Tarifa N° 2.

        Realiza la conversión dinámica a Unidades Tributarias (U.T.) para determinar 
        el tramo impositivo y el sustraendo aplicable cuando el concepto normativo 
        lo requiera, garantizando consistencia decimal y persistencia segura.
        """
        
        invoice = self.purchase_invoice
        fiscal_profile = getattr(invoice, "fiscal_profile", None)
        if not fiscal_profile:
            raise ValidationError(
                "La factura de compra asociada no posee un perfil fiscal (fiscal_profile) válido.",
                code="missing_fiscal_profile"
            )
    
        # Variables base para el cálculo financiero
        concept_choice = IslrPjndChoices(self.concepts_payment_pjnd)
        subtotal: Decimal = getattr(invoice, "subtotal", Decimal("0.00"))
        ut: Decimal = Decimal(str(ut_value))
        
        base_imponible: Decimal = concept_choice.base_imponible
        percentage_attr: str = concept_choice.percentage

        raw_withheld_amount = Decimal("0.00")

        # ESCENARIO A: El concepto corresponde a la escala progresiva "TARIFA N° 2"
        if percentage_attr == "TARIFA N° 2":
            monto_base_bs = subtotal * base_imponible
            monto_base_ut = monto_base_bs / ut

            # Evaluación de Tramos de la Matriz de la Tarifa N° 2
            if monto_base_ut <= Decimal("2000.00"):
                rate = Decimal("0.15")
                sustraendo_bs = Decimal("0.00")
            elif monto_base_ut <= Decimal("3000.00"):
                rate = Decimal("0.22")
                sustraendo_bs = Decimal("140.00") * ut
            else:
                rate = Decimal("0.34")
                sustraendo_bs = Decimal("500.00") * ut

            raw_withheld_amount = (monto_base_bs * rate) - sustraendo_bs
            raw_subtracting = sustraendo_bs

        # ESCENARIO B: Flujo Ordinario con Alícuota Fija
        else:
            sustraendo_bs = Decimal("0.00")
            rate = Decimal(percentage_attr)
            raw_withheld_amount = subtotal * base_imponible * rate
            raw_subtracting = sustraendo_bs

        # Sustracción Mínima: Forzar a 0.00 si el resultado es negativo por desbalances o redondeos
        if raw_withheld_amount < Decimal("0.00"):
            raw_withheld_amount = Decimal("0.00")

        # Política de Redondeo Financiero Estricto (ROUND_HALF_UP) a dos (2) posiciones decimales
        precision = Decimal("0.01")
        self.islr_withheld_amount = raw_withheld_amount.quantize(precision, rounding=ROUND_HALF_UP)
        self.subtracting = raw_subtracting.quantize(precision, rounding=ROUND_HALF_UP)
        
    def calculate_pjd_withholding(self) -> None:
        """
        Calcula y asigna de manera automática el impuesto neto retenido (islr_withheld_amount)
        para Personas Jurídicas Domiciliadas (PJD).

        El método valida las condiciones de integridad fiscal y procesa la retención 
        mediante una ecuación lineal directa utilizando el subtotal de la factura y 
        las propiedades del enumerador IslrPjdChoices, aplicando redondeo financiero estricto.
        """
        
        # 1. Variables y Origen de Datos
        concept_choice = IslrPjdChoices(self.concepts_payment_pjd)
        subtotal: Decimal = getattr(self.purchase_invoice, "subtotal", Decimal("0.00"))
        base_imponible: Decimal = concept_choice.base_imponible
        percentage: Decimal = concept_choice.percentage

        # 2. Algoritmo Operativo y Modelo Matemático
        # islr_withheld_amount = subtotal * base_imponible * percentage
        raw_withheld_amount = subtotal * base_imponible * percentage

        # 3. Redondeo y Precisión Fiscal (ROUND_HALF_UP a dos posiciones decimales)
        precision = Decimal("0.01")
        self.islr_withheld_amount = raw_withheld_amount.quantize(precision, rounding=ROUND_HALF_UP)
    
    def execute_withholding_routing(self) -> None:
        """Enrutador centralizado para identificar el concepto asignado y disparar su cálculo."""
        if self.concepts_payment_pnnr is not None:
            self.calculate_pnnr_withholding()
        elif self.concepts_payment_pnr is not None:
            self.calculate_pnr_withholding()
        elif self.concepts_payment_pjnd is not None:
            self.calculate_pjnd_withholding()
        elif self.concepts_payment_pjd is not None:
            self.calculate_pjd_withholding()
    
    def clean(self) -> None:
        """
        Ejecuta las validaciones de negocio a nivel de aplicación.
        
        Raises:
            ValidationError: Si alguna regla de integridad fiscal es vulnerada.
        """
        super().clean()
        errors: Dict[str, ValidationError] = {}

        # Validación de Factura Base
        if hasattr(self, 'purchase_invoice') and self.purchase_invoice:
            if self.purchase_invoice.status != 'PRELIMINARY':
                errors['purchase_invoice'] = ValidationError(
                    ("La factura asociada debe estar estrictamente en estado PRELIMINARY."),
                    code='invalid_invoice_status'
                )

        # Estructura Jerárquica del Correlativo del numero de documento
        if self.document_number and self.application_date:
            expected_prefix = self.application_date.strftime('%Y%m')
            if not re.match(rf'^{expected_prefix}\d+', self.document_number):
                errors['document_number'] = ValidationError(
                    ("El correlativo debe comenzar estrictamente con el formato YYYYMM (%(prefix)s) "
                      "correspondiente a la fecha de aplicación."),
                    params={'prefix': expected_prefix},
                    code='invalid_correlative_structure'
                )

        # Temporalidad Fiscal de la Operación
        if hasattr(self, 'purchase_invoice') and self.purchase_invoice and self.application_date:
            if self.application_date < self.purchase_invoice.date:
                errors['application_date'] = ValidationError(
                    ("La fecha de aplicación no puede ser cronológicamente inferior a la fecha "
                      "de emisión de la factura (%(invoice_date)s)."),
                    params={'invoice_date': self.purchase_invoice.date},
                    code='retroactive_application_date'
                )
        # Exclusividad Mutua de Conceptos de ISLR
        concept_fields = {
            'concepts_payment_pnnr': self.concepts_payment_pnnr,
            'concepts_payment_pnr': self.concepts_payment_pnr,
            'concepts_payment_pjnd': self.concepts_payment_pjnd,
            'concepts_payment_pjd': self.concepts_payment_pjd,
        }
        assigned_concepts = {k: v for k, v in concept_fields.items() if v is not None}

        if len(assigned_concepts) == 0:
            raise ValidationError(
                ("Debe seleccionar exactamente un concepto de retención de ISLR."),
                code='missing_islr_concept'
            )
        if len(assigned_concepts) > 1:
            raise ValidationError(
                ("Se han detectado múltiples conceptos de retención seleccionados. "
                  "Solo está permitido asignar uno."),
                code='multiple_islr_concepts'
            )

        if errors:
             raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Guarda la instancia controlando la inmutabilidad de los datos procesados.
        
        Raises:
            ValidationError: Si se intenta modificar un registro en estado PROCESSED.
        """
        if self.pk:
            original = IslrWithholdingCertificate.objects.get(pk=self.pk)
            if original.status == self.CertificateStatus.PROCESSED:
                raise ValidationError(
                    ("Bloqueo de Modificación: Este comprobante ya ha sido procesado "
                      "y su ciclo fiscal se encuentra cerrado."),
                    code='immutable_record_processed'
                )

        # Calculo automatico del atributo "islr_withheld_amount" y "subtracting"
        self.execute_withholding_routing()

        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> Tuple[int, Dict[str, int]]:
        """
        Impide la eliminación física si el registro se encuentra procesado.
        
        Raises:
            ValidationError: Si se intenta eliminar un registro en estado PROCESSED.
        """
        if self.status == self.CertificateStatus.PROCESSED:
            raise ValidationError(
                ("Bloqueo de Eliminación: No se permite la eliminación física de un "
                  "comprobante en estado PROCESSED por motivos de auditoría fiscal."),
                code='protected_record_processed'
            )
        return super().delete(*args, **kwargs)

    class Meta:
        """Configuración de metadatos del modelo ComprobanteRetencionISLR."""
    
        verbose_name = "ISLR Withholding Certificate"
        verbose_name_plural = "ISLR Withholding Certificates"
            
        # Restricción de Base de Datos para garantizar aislamiento multi-tenant
        constraints = [
            models.UniqueConstraint(
                fields=['document_number', 'fiscal_profile'],
                name='unique_document_per_fiscal_profile'
            )
        ]
    
    def __str__(self) -> str:
        """Retorna la representación en cadena del comprobante."""
        return f"{self.document_number} - {self.fiscal_profile}"
    