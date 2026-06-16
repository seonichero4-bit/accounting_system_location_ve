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

    class TipoContribuyente(models.TextChoices):
        """Opciones legales para la categorización del tipo de contribuyente."""

        FORMAL = "FORMAL", "Formal"
        ORDINARIO = "ORDINARIO", "Ordinario"
        ESPECIAL = "ESPECIAL", "Especial"

    entity = models.OneToOneField(
        EntityModel,
        on_delete=models.PROTECT,
        related_name="fiscal_profile",
        verbose_name="Entidad de Django Ledger",
    )
    codigo = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Código de Control Interno",
    )
    nombre = models.CharField(
        max_length=35,
        verbose_name="Nombre o Razón Social Legal",
    )
    rif = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Registro de Información Fiscal (RIF)",
    )
    nit = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="Número de Identificación Tributaria (NIT)",
    )
    tipo_contribuyente = models.CharField(
        max_length=15,
        choices=TipoContribuyente.choices,
        verbose_name="Tipo de Contribuyente",
    )

    def obtener_proveedor_por_rif(self, rif: str) -> Optional["ProveedorLocal"]:
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
            return self.proveedores_locales.get(rif=rif)
        except proveedores_locales.DoesNotExist:
            return None

    def crear_proveedor(self, **kwargs) -> "ProveedorLocal":
        """Crea y persiste un nuevo proveedor local asociado directamente a este perfil.

        Aprovecha la relación inversa para asegurar la asignación implícita
        de la clave foránea en la base de datos.

        Args:
            **kwargs: Diccionario de argumentos clave-valor para los campos del proveedor
                      (ej. codigo, nombre, rif).

        Returns:
            ProveedorLocal: La instancia del proveedor local recién creada.
        """
        return self.proveedores_locales.create(**kwargs)                 

    class Meta:
        """Configuración de metadatos del modelo FiscalProfile."""

        verbose_name = "Perfil Fiscal"
        verbose_name_plural = "Perfiles Fiscales"

    def __str__(self) -> str:
        """Retorna una representación legible del Perfil Fiscal."""
        return f"{self.nombre} ({self.rif})"


class FiscalModuleAbstractModel(models.Model):
    """Modelo abstracto para el control estricto de aislamiento multiusuario.

    Garantiza que cualquier entidad o transacción fiscal del sistema dependa
    jerárquicamente de un perfil fiscal obligatorio, previniendo fugas de
    información entre inquilinos en la base de datos PostgreSQL.
    """

    fiscal_profile = models.ForeignKey(
        FiscalProfile,
        on_delete=models.PROTECT,
        related_name="%(class)s_modules",
        verbose_name="Inquilino / Perfil Fiscal Asociado",
    )

    class Meta:
        """Configuración de metadatos para el modelo abstracto."""

        abstract = True