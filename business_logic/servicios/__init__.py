"""Paquete de servicios para la lógica de negocio fiscal.

Expone de forma centralizada las clases que encapsulan las reglas de 
negocio y operaciones transaccionales. Actúa como la interfaz de 
comunicación limpia entre la capa de presentación (vistas/formularios) 
y la capa de acceso a datos (modelos).
"""

from .proveedor_servicio import ProveedorService

__all__ = [
    "ProveedorService",
]