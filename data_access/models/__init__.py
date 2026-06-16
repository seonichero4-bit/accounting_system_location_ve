"""Módulo de inicialización del paquete de modelos de localización fiscal.

Importa y expone explícitamente todas las entidades relacionales, modelos
abstractos y perfiles multi-inquilino del módulo fiscal. Esto garantiza que
el motor de ORM de Django detecte, registre y genere correctamente las
migraciones sobre el backend de PostgreSQL.
"""

from .base import FiscalModuleAbstractModel, FiscalProfile
from .purchase_book import LibroComprasFactura, LineaFacturaCompra
from .supplier import ProveedorLocal
from .withholding import ComprobanteRetencionISLR, ComprobanteRetencionIVA

__all__ = [
    "FiscalProfile",
    "FiscalModuleAbstractModel",
    "ProveedorLocal",
    "LibroComprasFactura",
    "LineaFacturaCompra",
    "ComprobanteRetencionIVA",
    "ComprobanteRetencionISLR",
]