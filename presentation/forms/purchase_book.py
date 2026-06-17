from typing import Any
from django import forms
from django.forms import inlineformset_factory

from data_access.models.purchase_book import PurchaseLedgerInvoice, PurchaseInvoiceLine

class PurchaseLedgerInvoiceForm(forms.ModelForm):
    """
    Formulario de cabecera para el registro en el Libro de Compras.
    
    Mapea estrictamente los campos requeridos para la identificación del 
    documento fiscal, excluyendo de forma implícita (al usar 'fields') 
    cualquier campo autocalculado como totales o montos base.
    """
    
    class Meta:
        model = PurchaseLedgerInvoice
        fields = [
            'document_type', 
            'number', 
            'invoice_control', 
            'date', 
            'purchase_type'
        ]


# Factory para inyección dinámica de múltiples filas de detalle contable y comercial.
# Permite mantener la integridad referencial (Cabecera -> Líneas) en la interfaz.
PurchaseInvoiceLineFormSet = inlineformset_factory(
    parent_model=PurchaseLedgerInvoice,
    model=PurchaseInvoiceLine,
    fields=[
        'description', 
        'unit_price', 
        'units', 
        'discount_percentage', 
        'vat_rate', 
        'nature', 
        'applies_islr_withholding', 
        'islr_withholding_percentage', 
        'accounting_mapping'
    ],
    extra=1,
    can_delete=True
)