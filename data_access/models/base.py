"""Módulo base estructural para modelos fiscales multi-inquilino.

Define el perfil fiscal asociado a las entidades de contabilidad de Django Ledger
y proporciona un modelo abstracto para imponer un aislamiento estricto de datos
por cada inquilino (tenant) sobre el backend de PostgreSQL.
"""
from django.db import models
from django_ledger.models import EntityModel
from typing import Optional

class FiscalProfile(models.Model):
    """Modelo estructural central para la identificación fiscal.

    Conecta una entidad base de Django Ledger con sus atributos legales obligatorios,
    actuando como el núcleo de gobernanza de datos multi-inquilino del sistema.
    """

    class TaxpayerType(models.TextChoices):
        """Opciones legales para la categorización del tipo de contribuyente."""

        FORMAL = "FORMAL", "Formal"
        ORDINARY = "ORDINARY", "Ordinary"
        SPECIAL = "SPECIAL", "Special"

    entity = models.OneToOneField(
        EntityModel,
        on_delete=models.PROTECT,
        related_name="fiscal_profile",
        verbose_name="Django Ledger Entity",
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Internal Control Code",
    )
    name = models.CharField(
        max_length=35,
        verbose_name="Legal Name or Corporate Name",
    )
    rif = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Fiscal Information Registry (RIF)",
    )
    nit = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="Tax Identification Number (NIT)",
    )
    taxpayer_type = models.CharField(
        max_length=15,
        choices=TaxpayerType.choices,
        verbose_name="Taxpayer Type",
    )

    def get_supplier_by_rif(self, rif: str) -> Optional["LocalSupplier"]:
        """Obtiene un proveedor local asociado a esta instancia mediante su RIF.

        Utiliza el mánager de la relación inversa (related_name) para buscar
        dentro del conjunto limitado de este perfil fiscal.

        Args:
            rif (str): El Registro de Información Fiscal del proveedor.

        Returns:
            Optional[ProveedorLocal]: La instancia de ProveedorLocal si se encuentra,
            de lo contrario None.
        """

        try:
            return self.localsupplier_models.get(rif=rif)
        except self.localsupplier_models.model.DoesNotExist:
            return None
       
    def create_supplier(self, name: str, rif: str, **other_fields) -> "LocalSupplier":
        """Crea y persiste un nuevo proveedor local asociado directamente a este perfil.

        Aprovecha la relación inversa para asegurar la asignación implícita
        de la clave foránea en la base de datos.

        Args:
            **kwargs: Diccionario de argumentos clave-valor para los campos del proveedor
                      (ej. codigo, nombre, rif).

        Returns:
            ProveedorLocal: La instancia del proveedor local recién creada.
        """
        return self.localsupplier_models.create(
            fiscal_profile=self, 
            name=name,
            rif=rif,
            **other_fields
        )
                  
    class Meta:
        """Configuración de metadatos del modelo FiscalProfile."""

        verbose_name = "Fiscal Profile"
        verbose_name_plural = "Fiscal Profiles"

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