"""Módulo de formularios para la validación y cuadre del Libro de Compras.

Define PurchaseLedgerInvoiceForm utilizando la API nativa de Django ModelForm,
asegurando el cumplimiento estricto de las validaciones cruzadas temporales,
formatos de imprenta del SENIAT y consistencia aritmética decimal.
"""

import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django import forms
from django.core.exceptions import ValidationError

from data_access.models.purchase_book import PurchaseLedgerInvoice


class PurchaseLedgerInvoiceForm(forms.ModelForm):
    """Formulario robusto mapeado al modelo de Facturas del Libro de Compras.

    Gestiona la captura limpia de datos fiscales e intercepta descuadres
    aritméticos o caducidades de créditos fiscales antes de la persistencia.
    """

    igtf_base = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        label="Base Imponible IGTF",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    class Meta:
        """Configuraciones base y mapeo de campos del modelo."""

        model = PurchaseLedgerInvoice
        fields = [
            "supplier",
            "number",
            "invoice_control",
            "document_type",
            "purchase_type",
            "status",
            "date",
            "application_month_year",
            "affected_invoice",
            "import_form_number",
            "import_file_number",
            "exempt_amount",
            "taxable_base",
            "general_rate",
            "vat_amount",
            "igtf_amount",
            "total_purchase",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "application_month_year": forms.TextInput(attrs={"placeholder": "MM-YYYY", "class": "form-control"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Inicializa el formulario flexibilizando requerimientos sintácticos base.

        Delega las condiciones obligatorias cruzadas al método clean para un manejo
        personalizado de los errores de campo.
        """
        super().__init__(*args, **kwargs)
        self.fields["invoice_control"].required = False
        self.fields["affected_invoice"].required = False
        self.fields["import_form_number"].required = False
        self.fields["import_file_number"].required = False

    def clean_invoice_control(self) -> str:
        """Sanea y valida el formato del número de control de imprenta nacional.

        Returns:
            str: El número de control limpio sin espacios fantasmas.

        Raises:
            ValidationError: Si contiene caracteres especiales o espacios prohibidos.
        """
        invoice_control = self.cleaned_data.get("invoice_control", "")
        if invoice_control:
            invoice_control = invoice_control.strip()
            # Permitir únicamente caracteres alfanuméricos y guiones
            if not re.match(r"^[0-9A-Za-z\-]+$", invoice_control):
                raise forms.ValidationError(
                    "El número de control introducido contiene caracteres especiales o espacios inválidos."
                )
        return invoice_control

    def clean(self) -> dict[str, Any]:
        """Ejecuta las validaciones cruzadas temporales, lógicas y aritméticas fiscales.

        Returns:
            dict[str, Any]: El diccionario de datos limpios y normalizados.

        Raises:
            ValidationError: Si hay un descuadre en el gran total o caducidad legal.
        """
        cleaned_data = super().clean()

        document_type = cleaned_data.get("document_type")
        purchase_type = cleaned_data.get("purchase_type")
        invoice_date = cleaned_data.get("date")
        application_month_year = cleaned_data.get("application_month_year")

        # 1. Lógica de Notas de Crédito / Débito vs Facturas
        if document_type in [InvoiceDocumentType.CREDIT_NOTE, InvoiceDocumentType.DEBIT_NOTE]:
            if not cleaned_data.get("affected_invoice"):
                self.add_error(
                    "affected_invoice",
                    "Este campo es estrictamente obligatorio para registrar Notas de Crédito o Débito.",
                )
        elif document_type == InvoiceDocumentType.INVOICE:
            cleaned_data["affected_invoice"] = None

        # 2. Regla de Importaciones
        if purchase_type == PurchaseType.IMPORT:
            if not cleaned_data.get("import_form_number") or not cleaned_data.get("import_file_number"):
                raise forms.ValidationError(
                    "Para compras de Importación, los campos de número de formulario y expediente son obligatorios."
                )
            # Asignación Dinámica por ausencia de imprenta nacional
            cleaned_data["invoice_control"] = "N/A"
        else:
            # Compras INTERNAS
            cleaned_data["import_form_number"] = None
            cleaned_data["import_file_number"] = None
            if not cleaned_data.get("invoice_control"):
                self.add_error(
                    "invoice_control",
                    "El número de control de la factura es obligatorio para operaciones internas.",
                )

        # 3. Coherencia Temporal y Caducidad (Art. 24 Ley del IVA)
        if invoice_date and invoice_date > date.today():
            self.add_error("date", "La fecha de emisión no puede ser posterior a la fecha actual del sistema.")

        if invoice_date and application_month_year:
            if not re.match(r"^(0[1-9]|1[0-2])-\d{4}$", application_month_year):
                self.add_error("application_month_year", "El formato del período fiscal debe ser estrictamente MM-YYYY.")
            else:
                month_str, year_str = application_month_year.split("-")
                p_month, p_year = int(month_str), int(year_str)

                if p_year < invoice_date.year or (p_year == invoice_date.year and p_month < invoice_date.month):
                    self.add_error(
                        "application_month_year",
                        "El período fiscal de aplicación no puede ser cronológicamente anterior a la fecha de emisión.",
                    )

                period_first_day = date(p_year, p_month, 1)
                months_diff = (period_first_day.year - invoice_date.year) * 12 + (
                    period_first_day.month - invoice_date.month
                )
                if months_diff > 12:
                    raise forms.ValidationError(
                        "El derecho al crédito fiscal de esta factura ha caducado por superar los 12 meses (Art. 24 Ley del IVA)."
                    )

        # 4. Integridad Matemática y Aritmética Fiscal (Uso estricto de Decimal)
        exempt_amount = cleaned_data.get("exempt_amount") or Decimal("0.00")
        taxable_base = cleaned_data.get("taxable_base") or Decimal("0.00")
        general_rate = cleaned_data.get("general_rate") or Decimal("16.00")
        vat_amount = cleaned_data.get("vat_amount") or Decimal("0.00")
        igtf_amount = cleaned_data.get("igtf_amount") or Decimal("0.00")
        igtf_base = cleaned_data.get("igtf_base") or Decimal("0.00")
        total_purchase = cleaned_data.get("total_purchase") or Decimal("0.00")

        # Validación Teórica de la Alícuota del IVA
        expected_vat = (taxable_base * (general_rate / Decimal("100.00"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if vat_amount != expected_vat:
            self.add_error(
                "vat_amount",
                f"El IVA introducido ({vat_amount}) difiere del cálculo teórico esperado ({expected_vat}).",
            )

        # Validación de la Alícuota Legal del IGTF (3%)
        if igtf_base > Decimal("0.00"):
            expected_igtf = (igtf_base * Decimal("0.03")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if igtf_amount != expected_igtf:
                self.add_error(
                    "igtf_amount",
                    f"El monto de IGTF ({igtf_amount}) no coincide con la alícuota legal del 3% ({expected_igtf}).",
                )

        # Validación del Cuadre General Obligatorio
        expected_total = exempt_amount + taxable_base + vat_amount + igtf_amount
        if total_purchase != expected_total:
            discrepancy = (total_purchase - expected_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            raise forms.ValidationError(
                f"Error de Cuadre Fiscal: El Gran Total ingresado ({total_purchase}) no coincide con la sumatoria exacta "
                f"de sus componentes ({expected_total}). Descuadre registrado: {discrepancy}."
            )

        return cleaned_data