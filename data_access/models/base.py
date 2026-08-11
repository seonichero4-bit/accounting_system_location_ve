"""Módulo base estructural para modelos fiscales multi-inquilino.

Define el perfil fiscal asociado a las entidades de contabilidad de Django Ledger
y proporciona un modelo abstracto para imponer un aislamiento estricto de datos
por cada inquilino (tenant) sobre el backend de PostgreSQL.
"""

import calendar
from typing import Optional, Any

from django_ledger.models import EntityModel, LedgerModel, AccountModel
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

from data_access.models.fiscalperiod import FiscalPeriod
from data_access.manager.requestscopedmanager import RequestScopedManager

# Validador de formato oficial para el RIF venezolano (Capa de Aplicación)
rif_format_validator = RegexValidator(
    regex=r'^[VEJGPC]\d{8,9}$',
    message="El RIF debe cumplir con el formato oficial venezolano (una letra [V, E, J, G, P, C] seguida de 8 a 9 dígitos numéricos sin guiones ni espacios).",
    code="invalid_rif_format"
)


class FiscalProfile(models.Model):
    """Modelo estructural central para la identificación fiscal.

    Conecta una entidad base de Django Ledger con sus atributos legales obligatorios
    y su mapa de cuentas de control para la contabilización en lote, actuando como
    el núcleo de gobernanza de datos multi-inquilino del sistema.
    """

    class TaxpayerType(models.TextChoices):
        """Opciones legales para la categorización del tipo de contribuyente."""

        FORMAL = "FORMAL", "Formal"
        ORDINARY = "ORDINARY", "Ordinary"
        SPECIAL = "SPECIAL", "Special"

    # --- Relación con la Entidad Base de Django Ledger ---
    entity = models.OneToOneField(
        EntityModel,
        on_delete=models.CASCADE,
        related_name="fiscalprofile",
        verbose_name="entity model ledger",
        null=True,  # argumento debe ser eliminado antes de producción 
        blank=True,  # argumento debe ser eliminado antes de producción 
    )
    name = models.CharField(
        max_length=250,
        verbose_name="Legal Name or Corporate Name",
        null=True,  # argumento debe ser eliminado antes de producción 
        blank=True,  # argumento debe ser eliminado antes de producción 
    )
    rif = models.CharField(
        max_length=20,
        validators=[rif_format_validator],
        verbose_name="Fiscal Information Registry (RIF)",
    )
    taxpayer_type = models.CharField(
        max_length=15,
        choices=TaxpayerType.choices,
        verbose_name="Taxpayer Type",
    )
    initial_fiscal_period = models.ForeignKey(
        FiscalPeriod,
        on_delete=models.PROTECT,
        related_name="fiscal_profiles",
        verbose_name="Initial Fiscal Period",
        null=True,
        blank=True,
        help_text="Periodo fiscal de inicio asignado a este perfil.",
    )
    

    # --- Configuración de Libro Mayor y Cuentas de Control (Django Ledger) ---
    ledger = models.ForeignKey(
        LedgerModel,
        on_delete=models.PROTECT,
        related_name="fiscal_profiles",
        verbose_name="Principal Ledger Model",
        null=True,
        blank=True,
        help_text="Libro Mayor General principal asignado a este perfil fiscal para el registro de asientos.",
    )
    inventory_account = models.ForeignKey(
        AccountModel,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Inventory Account",
        null=True,
        blank=True,
        help_text="Cuenta contable de control para Inventario de Mercancía.",
    )
    vat_credit_account = models.ForeignKey(
        AccountModel,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="VAT Credit Account",
        null=True,
        blank=True,
        help_text="Cuenta contable de control para IVA Crédito Fiscal Computable.",
    )
    igtf_expense_account = models.ForeignKey(
        AccountModel,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="IGTF Expense Account",
        null=True,
        blank=True,
        help_text="Cuenta contable de gasto para IGTF Pagado en Compras.",
    )
    islr_payable_account = models.ForeignKey(
        AccountModel,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="ISLR Payable Account",
        null=True,
        blank=True,
        help_text="Cuenta contable de pasivo para Retención de ISLR por Pagar.",
    )
    cxp_suppliers_account = models.ForeignKey(
        AccountModel,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Accounts Payable Suppliers Account",
        null=True,
        blank=True,
        help_text="Cuenta contable de pasivo comercial Cuentas por Pagar Proveedores.",
    )
    vat_withheld_payable_account = models.ForeignKey(
        AccountModel,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="VAT Withheld Payable Account",
        null=True,
        blank=True,
        help_text="Cuenta contable de pasivo fiscal para IVA Retenido por Enterar al SENIAT.",
    )

    objects = RequestScopedManager()

    def get_supplier_by_rif(self, rif: str) -> Optional["LocalSupplier"]:
        """Obtiene un proveedor local asociado a esta instancia mediante su RIF.

        Utiliza el mánager de la relación inversa (related_name) para buscar
        dentro del conjunto limitado de este perfil fiscal.

        Args:
            rif (str): El Registro de Información Fiscal del proveedor.

        Returns:
            Optional[LocalSupplier]: La instancia de LocalSupplier si se encuentra,
            de lo contrario None.
        """
        try:
            return self.localsupplier_models.get(rif=rif)
        except self.localsupplier_models.model.DoesNotExist:
            return None
       
    def clean(self) -> None:
        """Realiza el saneamiento, normalización activa y validaciones del modelo.

        Limpia las cadenas de texto, elimina variaciones estéticas de formato en el RIF
        para mitigar duplicados colaterales y garantiza la existencia legal de la entidad base
        así como la consistencia del Plan de Cuentas asociado.

        Raises:
            ValidationError: Si alguna restricción lógica o relacional del negocio es violada.
        """
        super().clean()
        errors: dict[str, str] = {}

        # 1. Saneamiento y Normalización Activa del RIF
        if self.rif:
            self.rif = self.rif.replace("-", "").replace(" ", "").upper()
            try:
                rif_format_validator(self.rif)
            except ValidationError as e:
                errors["rif"] = e.messages

        # 2. Saneamiento del campo Name
        if self.name:
            self.name = self.name.strip()

        # 3. Validación de Existencia Formal de la Relación de Entidad
        if self.entity_id:
            if not EntityModel.objects.filter(pk=self.entity_id).exists():
                errors["entity"] = "La instancia seleccionada de EntityModel no existe formalmente en el sistema."

    def save(self, *args, **kwargs) -> None:
        """Restricción a nivel de modelo: impide cambiar el periodo fiscal de inicio

        si el periodo actual está en estatus 'procesado'.
        """
        if self.pk:
            original = FiscalProfile.objects.filter(pk=self.pk).first()
            if (
                original
                and original.initial_fiscal_period
                and original.initial_fiscal_period.status == FiscalPeriod.Status.PROCESSED
            ):
                if self.initial_fiscal_period_id != original.initial_fiscal_period_id:
                    raise ValidationError(
                        {"initial_fiscal_period": "No se puede modificar el periodo fiscal de inicio cuando su estatus es 'procesado'."}
                    )

       # Validar tipo de contribuyente vs. frecuencia de periodo fiscal
        if self.initial_fiscal_period and self.initial_fiscal_period.start_period:
            start_date = self.initial_fiscal_period.start_period
            _, last_day = calendar.monthrange(start_date.year, start_date.month)
            day = start_date.day

            if self.taxpayer_type == self.TaxpayerType.SPECIAL:
                if day not in (15, last_day):
                    raise ValidationError(
                        {
                            "initial_fiscal_period": (
                                "Los contribuyentes de tipo Especial deben manejar periodos fiscales quincenales "
                                "(fecha de inicio el día 15 o a final de mes)."
                            )
                        }
                    )
            elif self.taxpayer_type in (self.TaxpayerType.ORDINARY, self.TaxpayerType.FORMAL):
                if day != 1:
                    raise ValidationError(
                        {
                            "initial_fiscal_period": (
                                "Los contribuyentes de tipo Ordinario y Formal deben manejar periodos fiscales mensuales "
                                "(fecha de inicio el día 01 del mes)."
                            )
                        }
                    )

        super().save(*args, **kwargs)
        
    class Meta:
        """Configuración de metadatos del modelo FiscalProfile."""

        verbose_name = "Fiscal Profile"
        verbose_name_plural = "Fiscal Profiles"

        constraints = [
            # Capa de Base de Datos: Restricción de Unicidad Absoluta del RIF
            models.UniqueConstraint(
                fields=["rif"],
                name="%(app_label)s_%(class)s_unique_rif"
            ),
            
            # Restricciones de Integridad de Datos Existentes
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="%(app_label)s_%(class)s_name_not_empty"
            ),
            models.CheckConstraint(
                condition=~models.Q(rif=""),
                name="%(app_label)s_%(class)s_rif_not_empty"
            ),
        ]

    def __str__(self) -> str:
        """Retorna una representación legible del Perfil Fiscal."""
        return f"{self.name} ({self.rif})"


class FiscalModuleAbstractModel(models.Model):
    """Modelo abstracto para el control estricto de aislamiento multiusuario.

    Garantiza que cualquier entidad o transacción fiscal del sistema dependa
    jerárquicamente de un perfil fiscal obligatorio, previniendo fugas de
    información entre inquilinos en la base de datos PostgreSQL.
    """

    fiscal_profile = models.ForeignKey(
        FiscalProfile,
        on_delete=models.PROTECT,
        related_name="%(class)s_models",
        verbose_name="Tenant / Associated Fiscal Profile",
    )

    class Meta:
        """Configuración de metadatos para el modelo abstracto."""

        abstract = True

    def __str__(self) -> str:
        """Retorna una representación legible del Perfil fiscal."""
        return f"{self.name} ({self.rif}) - {self.pk}"