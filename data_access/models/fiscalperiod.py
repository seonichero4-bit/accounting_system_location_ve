from django.core.exceptions import ValidationError
from django.db import models

class FiscalPeriod(models.Model):
    """Modelo para registrar los periodos fiscales mensuales de una empresa."""

    class Status(models.TextChoices):
        PRELIMINARY = "preliminar", "Preliminar"
        PROCESSED = "procesado", "Procesado"

    # Campo 1: Periodo fiscal de inicio
    start_period = models.DateField(
        verbose_name="Periodo Fiscal de Inicio",
        help_text="Fecha o periodo fiscal inicial."
    )
    # Campo 2: Periodos posteriores
    subsequent_period = models.DateField(
        null=True,
        blank=True,
        verbose_name="Periodo Fiscal Posterior",
        help_text="Periodo fiscal subsecuente."
    )
    # Campo 3: Estatus del periodo
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.PRELIMINARY,
        verbose_name="Estatus del Periodo"
    )

    def save(self, *args, **kwargs) -> None:
        """Restringe la modificación de un período fiscal cuando su estatus es 'procesado'."""
        if self.pk:
            original = FiscalPeriod.objects.filter(pk=self.pk).first()
            if original and original.status == self.Status.PROCESSED:
                if self.start_period != original.start_period:
                    raise ValidationError(
                        {"start_period": "No se puede modificar la fecha de inicio de un periodo fiscal con estatus 'procesado'."}
                    )
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Fiscal Period"
        verbose_name_plural = "Fiscal Periods"

    def __str__(self) -> str:
        return f"{self.start_period} ({self.get_status_display()})"