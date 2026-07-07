"""Módulo base estructural para modelos fiscales multi-inquilino.

Define el perfil fiscal asociado a las entidades de contabilidad de Django Ledger
y proporciona un modelo abstracto para imponer un aislamiento estricto de datos
por cada inquilino (tenant) sobre el backend de PostgreSQL.
"""
from typing import Optional, Any

from django_ledger.models import EntityModel
from django.db import models, transaction
from django.contrib.auth.models import User

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
        on_delete=models.CASCADE,
        related_name="fiscalprofile",
        verbose_name="entity model ledger",
        null=True, #argumento debe ser eliminado ante de produccion 
        blank=True, #argumento debe ser eliminado ante de produccion 
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Internal Control Code",
    )
    name = models.CharField(
        max_length=35,
        verbose_name="Legal Name or Corporate Name",
         null=True, #argumento debe ser eliminado ante de produccion 
        blank=True, #argumento debe ser eliminado ante de produccion 
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

    @classmethod
    def create_profile(
        cls,
        admin: 'User',
        entity_name: str,
        use_accrual_method: bool,
        fy_start_month: int,
        rif: str,
        code: str,
        taxpayer_type: str,
        nit: Optional[str] = None,
    ) -> "FiscalProfile":
        """Crea un perfil fiscal y su entidad contable asociada de forma atómica.

        Gestiona la creación del inquilino (tenant) instanciando primero el 
        EntityModel requerido por Django Ledger utilizando obligatoriamente el nombre 
        provisto, y posteriormente el FiscalProfile de forma atómica.

        Args:
            admin (Any): Instancia del usuario administrador (User) para la entidad de Ledger.
            entity_name (str): Nombre explícito y legal para la entidad contable (EntityModel).
            rif (str): Registro de Información Fiscal.
            code (str): Código de control interno único.
            taxpayer_type (str): Tipo de contribuyente (ej. 'ORDINARY').
            nit (Optional[str], optional): Número de Identificación Tributaria.
            **entity_kwargs (Any): Argumentos adicionales para EntityModel.create_entity 
                (ej. use_accrual_method, fy_start_month).

        Returns:
            FiscalProfile: La instancia del perfil fiscal recién creada.
        """
        with transaction.atomic():
           
            entity = EntityModel.create_entity(
                name=entity_name,
                admin=admin,
                use_accrual_method=use_accrual_method,
                fy_start_month=fy_start_month
            )

            profile = cls.objects.create(
                entity=entity,
                name=entity_name,
                code=code,
                rif=rif,
                nit=nit,
                taxpayer_type=taxpayer_type
            )
            
            return profile

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

        constraints = [
            # 1. Restricciones de Integridad de Datos
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="%(app_label)s_%(class)s_name_not_empty"
            ),
            models.CheckConstraint(
                condition=~models.Q(rif=""),
                name="%(app_label)s_%(class)s_rif_not_empty"
            ),
             models.CheckConstraint(
                condition=~models.Q(code=""),
                name="%(app_label)s_%(class)s_code_not_empty"
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