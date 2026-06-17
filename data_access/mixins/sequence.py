"""Módulo de mixins para la gestión de secuencias numéricas y alfanuméricas.

Proporciona abstracciones reutilizables para inyectar capacidades de generación
automática de códigos y números de documento bajo una arquitectura multi-inquilino.
Agrupa la lógica tanto para datos maestros como para datos transaccionales.
"""

from typing import Any
from django.db import models
from django.utils import timezone


class AutomaticCodeMixin:
    """Mixin para automatizar la generación de códigos correlativos alfanuméricos.

    Extrae la lógica de persistencia y cálculo del secuencial para mantener
    los modelos limpios y desacoplados. Está diseñado para ser implementado
    principalmente en modelos de datos maestros ("Master Data") como Proveedores,
    Clientes, Artículos, entre otros.

    Importante: El modelo que herede de este mixin DEBE definir explícitamente
    un atributo 'code' (CharField) y configurar una restricción
    'unique_together = ("fiscal_profile", "code")' en su clase Meta
    para garantizar el aislamiento multi-inquilino, y poseer una relación
    jerárquica con 'FiscalProfile'.
    """

    class CodePrefixes(models.TextChoices):
        """Opciones de prefijos por defecto para las entidades del sistema."""

        PROVEEDORES = "PROV", "Proveedores"
        CLIENTES = "CLI", "Clientes"
        ARTICULOS = "ITEM", "Articulos"
        FACTURA_COMPRA = "FAC-COM", "Factura de compra"

    # Propiedades configurables sobrescribibles por las clases hijas o modelos contenedores
    '''
    PREFIX = CodePrefixes.PROVEEDORES
    PADDING_LENGTH = 5
    '''

    def generate_next_code(self) -> str:
        """Calcula de forma segura el siguiente código alfanumérico disponible.

        Filtra los registros existentes correspondientes a la clase específica
        y al perfil fiscal actual, extrayendo la porción numérica del último
        código emitido ordenado por ID.

        Returns:
            str: El código formateado final (ej. 'PROV-00001').
        """
        # Se obtiene la clase del modelo que está usando el mixin de manera dinámica
        model_class = self.__class__
        
        last_record = (
            model_class.objects.filter(fiscal_profile=self.fiscal_profile)
            .order_by("id")
            .last()
        )

        next_number = 1
        if last_record and hasattr(last_record, "code") and last_record.code:
            try:
                # Extrae la última sección numérica después del delimitador '-'
                numeric_part = last_record.code.split("-")[-1]
                next_number = int(numeric_part) + 1
            except (ValueError, IndexError, AttributeError):
                # Fallback seguro en caso de corrupción o cambio manual previo del string
                next_number = 1

        return f"{self.PREFIX}-{next_number:0{self.PADDING_LENGTH}d}"

    def handle_automatic_code(self) -> None:
        """Asigna el código autogenerado a la entidad si cumple los requisitos.

        Verifica si la instancia está en fase de creación (sin Clave Primaria)
        y si el atributo 'code' se encuentra vacío.
        """
        if not self.pk and hasattr(self, "code") and not self.code:
            self.code = self.generate_next_code()


class TransactionalSequenceMixin:
    """Mixin para automatizar la generación de códigos correlativos transaccionales.

    Inyecta la lógica necesaria para calcular secuencias numéricas complejas
    con formato fiscal periódico. Diseñado para ser implementado exclusivamente
    en modelos de datos transaccionales ("Transactional Data") como Comprobantes
    de Retención, Notas de Crédito y Notas de Débito.

    Importante: El modelo que herede de este mixin DEBE definir explícitamente
    un atributo 'document_number' (CharField) y configurar una restricción
    'unique_together = ("fiscal_profile", "document_number")' en su clase Meta
    para garantizar el aislamiento multi-inquilino, y poseer una relación
    jerárquica con 'FiscalProfile'.
    """

    class TransactionPrefixes(models.TextChoices):
        """Opciones de prefijos fiscales para documentos transaccionales."""

        RETENCION_IVA = "RET_IVA", "Comprobante de Retención de IVA"
        RETENCION_ISLR = "RET_ISLR", "Comprobante de Retención de ISLR"
        NOTA_CREDITO = "NC", "Nota de Crédito"
        NOTA_DEBITO = "ND", "Nota de Débito"

    # Propiedades configurables por los modelos transaccionales hijos
    '''
    PREFIX = TransactionPrefixes.RETENCION
    PADDING_LENGTH = 5
    '''

    def generate_next_document_number(self) -> str:
        """Calcula el siguiente número de documento transaccional disponible.

        Filtra por la clase del modelo definitivo y el perfil fiscal asignado,
        obteniendo el último registro ordenado por ID para extraer e incrementar
        la sección numérica final de forma aislada y segura.

        Returns:
            str: El número de documento formateado (ej. 'RET-202606-00001').
        """
        model_class = self.__class__

        last_record = (
            model_class.objects.filter(fiscal_profile=self.fiscal_profile)
            .order_by("id")
            .last()
        )

        next_number = 1
        if last_record and hasattr(last_record, "document_number") and last_record.document_number:
            try:
                # Extrae la sección numérica final (último elemento tras separar por '-')
                numeric_part = last_record.document_number.split("-")[-1]
                next_number = int(numeric_part) + 1
            except (ValueError, IndexError, AttributeError):
                # Resguardo seguro si ocurre una alteración inesperada del formato de cadena
                next_number = 1

        # Obtención del periodo actual formateado como AñoMes (AAAAMM)
        current_period = timezone.now().strftime("%Y%m")

        return f"{self.PREFIX}-{current_period}-{next_number:0{self.PADDING_LENGTH}d}"

    def handle_transactional_code(self) -> None:
        """Asigna el número correlativo de documento transaccional a la instancia.

        Verifica que el registro se encuentre en fase de inserción inicial (sin PK)
        y que no se haya establecido previamente un número de documento.
        """
        if not self.pk and hasattr(self, "document_number") and not self.document_number:
            self.document_number = self.generate_next_document_number()