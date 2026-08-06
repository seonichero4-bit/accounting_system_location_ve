from django_ledger.io import ACCOUNT_CHOICES_NO_ROOT
from django_ledger.models import ChartOfAccountModel
from django_ledger.models.accounts import AccountModel
from django.forms import ModelForm, HiddenInput


class AccountCreateForm(ModelForm):
   
    def __init__(self, coa_model: ChartOfAccountModel, *args, **kwargs):

        # Asignar a initial si no está presente
        initial = kwargs.get('initial', {})
        initial['coa_model'] = coa_model
        kwargs['initial'] = initial
        
        self.COA_MODEL: ChartOfAccountModel = coa_model
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = ACCOUNT_CHOICES_NO_ROOT
        self.fields['code'].required = False
        self.fields['coa_model'].disabled = True
        self.fields['coa_model'].required = True
        
    def clean_role_default(self):
        role_default = self.cleaned_data['role_default']
        if not role_default:
            return None
        return role_default

    def clean_coa_model(self):
        return self.COA_MODEL

    class Meta:
        model = AccountModel
        fields = [
            'code',
            'name',
            'role',
            'role_default',
            'balance_type',
            'active',
            'coa_model',
        ]
        widgets = {
    
            'coa_model': HiddenInput(),
        }

