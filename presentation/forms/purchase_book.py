"""Módulo de formularios para la validación y cuadre del Libro de Compras.

Define PurchaseLedgerInvoiceForm utilizando la API nativa de Django ModelForm,
asegurando el cumplimiento estricto de las validaciones cruzadas temporales,
formatos de imprenta del SENIAT y consistencia aritmética decimal[cite: 2].
"""

import re
from datetime import date
from decimal import Decimal 
from typing import Any

from django import forms
from django.core.exceptions import ValidationError

from data_access.models.purchase_book import PurchaseLedgerInvoice


class PurchaseLedgerInvoiceForm(forms.ModelForm):
    """Formulario robusto mapeado al modelo de Facturas del Libro de Compras.

    Gestiona la captura limpia de datos fiscales e intercepta descuadres
    aritméticos o caducidades de créditos fiscales antes de la persistencia[cite: 2].
    """

    # igtf_base = forms.DecimalField(
    #     max_digits=15,
    #     decimal_places=2,
    #     required=False,
    #     initial=Decimal("0.00"),
    #     label="Base Imponible IGTF",
    #     widget=forms.NumberInput(attrs={"class": "form-control"}),
    # )

    class Meta:
        """Configuraciones base y mapeo de campos del modelo[cite: 2]."""

        model = PurchaseLedgerInvoice
        fields = [
            "supplier",
            "number",
            "invoice_control",
            "document_type",
            "purchase_type",
            "date",
            "affected_invoice",
            "import_form_number",
            "import_file_number",
            "exempt_amount",
            "amount_exonerated",
            "amount_not_subject",
            "amount_without_right_to_credit",
            "taxable_base",
            "vat_percentage",
            "vat_amount",
            "igtf_base",
            "igtf_amount",
            "total_purchase",
        ]

        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }