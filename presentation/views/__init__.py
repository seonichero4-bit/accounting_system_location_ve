"""Paquete de vistas para la capa de presentación fiscal.

Este módulo inicializa el directorio de vistas como un paquete de Python.
Expone las clases de las vistas utilizando importaciones relativas para 
mantener un espacio de nombres limpio y acoplarse correctamente a la 
nueva arquitectura de directorios.
"""

from .supplier import (
    LocalSupplierCreateView,
    LocalSupplierDeleteView,
    LocalSupplierDetailView,
    LocalSupplierListView,
    LocalSupplierUpdateView,
)

__all__ = [
    "LocalSupplierCreateView",
    "LocalSupplierDeleteView",
    "LocalSupplierDetailView",
    "LocalSupplierListView",
    "LocalSupplierUpdateView",
]