"""Módulo de inicialización del paquete de modelos de localización fiscal.

Importa y expone explícitamente todas las entidades relacionales, modelos
abstractos y perfiles multi-inquilino del módulo fiscal. Esto garantiza que
el motor de ORM de Django detecte, registre y genere correctamente las
migraciones sobre el backend de PostgreSQL.
"""

from .base import FiscalModuleAbstractModel, FiscalProfile
from .purchase_book import PurchaseLedgerInvoice#, PurchaseInvoiceLine
from .supplier import LocalSupplier
from .withholding import IslrWithholdingCertificate, VatWithholdingCertificate

__all__ = [
    "FiscalProfile",
    "FiscalModuleAbstractModel",
    "LocalSupplier",
    "PurchaseLedgerInvoice",
    "PurchaseInvoiceLine",
    "VatWithholdingCertificate",
    "IslrWithholdingCertificate",
]