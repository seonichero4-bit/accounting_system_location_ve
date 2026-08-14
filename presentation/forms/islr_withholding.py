
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
        fields = ["document_number", 
                  "application_date", 
                  "concepts_payment_pnnr", 
                  "concepts_payment_pnr", 
                  "concepts_payment_pjnd", 
                  "concepts_payment_pjd"

        ]

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     self.fields['fiscal_period'].required = False