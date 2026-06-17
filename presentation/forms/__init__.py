"""Paquete de formularios para la capa de presentación de localización fiscal.

Expone de forma centralizada los formularios de Django mapeados a los modelos
de proveedores locales y libro de compras, facilitando una interfaz limpia
para las vistas de la aplicación.
"""
from .purchase_book import PurchaseLedgerInvoiceForm
from .supplier import LocalSupplierForm

__all__ = [
    "LocalSupplierForm",
    "PurchaseLedgerInvoiceForm",
]