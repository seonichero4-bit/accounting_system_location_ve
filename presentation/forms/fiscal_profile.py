"""Módulo de formularios para la gestión de perfiles fiscales, entidades contables y periodos fiscales."""

import calendar
from datetime import datetime
from typing import Any, Optional

from django import forms

from data_access.models.base import FiscalProfile, FiscalPeriod
from django_ledger.models import EntityModel, LedgerModel, AccountModel


class FiscalPeriodForm(forms.ModelForm):
    """Formulario para la definición del periodo fiscal inicial."""

    start_period = forms.DateField(
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "type": "date",
                "class": "form-control",
            },
        ),
        input_formats=["%Y-%m-%d"],
        label="Periodo Fiscal de Inicio",
        help_text="Seleccione la fecha de inicio del período",
    )

    class Meta:
        """Metadatos del formulario."""
        
        model = FiscalPeriod
        fields = ["start_period"]

    def __init__(self, *args: Any, taxpayer_type: Optional[str] = None, **kwargs: Any) -> None:
        """Inicializa el formulario integrando el tipo de contribuyente para validaciones lógicas."""
        self.taxpayer_type = taxpayer_type
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.start_period:
            self.initial["start_period"] = self.instance.start_period.strftime("%Y-%m-%d")

    def clean_start_period(self) -> Optional[datetime.date]:
        """Sanea y valida la fecha de inicio basándose en la categorización del contribuyente."""
        data = self.cleaned_data.get("start_period")
        if not data:
            return None

        if isinstance(data, str):
            try:
                data = datetime.strptime(data, "%Y-%m-%d").date()
            except ValueError as error:
                raise forms.ValidationError("Formato de fecha inválido. Use el formato YYYY-MM-DD.") from error

        year = data.year
        month = data.month
        day = data.day
        _, last_day = calendar.monthrange(year, month)

        if self.taxpayer_type:
            if self.taxpayer_type in [FiscalProfile.TaxpayerType.FORMAL, FiscalProfile.TaxpayerType.ORDINARY]:
                if day != 1:
                    raise forms.ValidationError(
                        "Para contribuyentes de tipo Ordinario y Formal (periodos mensuales), "
                        "la fecha de inicio debe ser el día 01 del mes."
                    )
            elif self.taxpayer_type == FiscalProfile.TaxpayerType.SPECIAL:
                if day not in (15, last_day):
                    raise forms.ValidationError(
                        "Para contribuyentes de tipo Especial (periodos quincenales), "
                        "la fecha de inicio debe ser el día 15 o el final de mes."
                    )
        else:
            if day not in (1, 15, last_day):
                raise forms.ValidationError(
                    "La fecha debe ser inicio de mes (día 01) para periodos mensuales, "
                    "o día 15 / final de mes para periodos quincenales."
                )

        return data


class FiscalProfileForm(forms.ModelForm):
    """Formulario mapeado al modelo FiscalProfile para el control tributario y contable."""

    class Meta:
        """Metadatos del formulario."""
        
        model = FiscalProfile
        fields = [
            "name",
            "rif",
            "taxpayer_type",
            "ledger",
            "inventory_account",
            "vat_credit_account",
            "igtf_expense_account",
            "islr_payable_account",
            "cxp_suppliers_account",
            "vat_withheld_payable_account",
        ]

    def __init__(self, *args: Any, is_update: bool = False, **kwargs: Any) -> None:
        """Inicializa el formulario inyectando el usuario y un flag de actualización.
        
        Si is_update es False, se eliminan los campos de configuración contable del formulario,
        ya que estos solo deben renderizarse y procesarse en la vista de actualización.
        Si is_update es True, se acotan los querysets de contabilidad basándose en las entidades del usuario.
        """
        super().__init__(*args, **kwargs)
        
        ledger_fields = [
            "ledger",
            "inventory_account",
            "vat_credit_account",
            "igtf_expense_account",
            "islr_payable_account",
            "cxp_suppliers_account",
            "vat_withheld_payable_account",
        ]

        # Si no es actualización (es creación), removemos los campos del formulario
        if not is_update:
            for field in ledger_fields:
                if field in self.fields:
                    self.fields.pop(field)
                    
        # Si es actualización, aplicamos los filtros
        if "ledger" in self.fields:
            self.fields["ledger"].queryset = LedgerModel.objects.filter(entity__fiscalprofile=self.instance)

            account_qs = AccountModel.objects.filter(coa_model__entity__fiscalprofile=self.instance)
            
            for field in ledger_fields:
                if field != "ledger" and field in self.fields:
                    self.fields[field].queryset = account_qs


class EntityModelForm(forms.ModelForm):
    """Formulario mapeado al modelo EntityModel de Django Ledger."""

    use_accrual_method = forms.BooleanField(initial=True, required=False)
    fy_start_month = forms.IntegerField(initial=12, min_value=1, max_value=12)

    class Meta:
        """Metadatos del formulario."""
        
        model = EntityModel
        fields = ["name"]