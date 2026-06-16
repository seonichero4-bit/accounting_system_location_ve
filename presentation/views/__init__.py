"""Paquete de vistas para la capa de presentación fiscal.

Este módulo inicializa el directorio de vistas como un paquete de Python.
Expone las clases de las vistas utilizando importaciones relativas para 
mantener un espacio de nombres limpio y acoplarse correctamente a la 
nueva arquitectura de directorios.
"""

from .supplier import (
    ProveedorLocalCreateView,
    ProveedorLocalDeleteView,
    ProveedorLocalDetailView,
    ProveedorLocalListView,
    ProveedorLocalUpdateView,
)

__all__ = [
    "ProveedorLocalCreateView",
    "ProveedorLocalDeleteView",
    "ProveedorLocalDetailView",
    "ProveedorLocalListView",
    "ProveedorLocalUpdateView",
]