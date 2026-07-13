
from django import forms

from data_access.models.base import FiscalProfile
from data_access.models.islr_withholding import IslrWithholdingCertificate
from data_access.models.purchase_book import PurchaseLedgerInvoice

class IslrWithholdingCertificateForm(forms.ModelForm):
    """Formulario estructural para el modelo IslrWithholdingCertificate.

    Excluye campos de control interno manejados de forma programática por la vista.
    """

    class Meta:
        """Metadatos de configuración del formulario."""

        model = IslrWithholdingCertificate
        exclude = ["fiscal_profile", "purchase_invoice"]