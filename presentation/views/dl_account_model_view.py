from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.edit import FormView
from django_ledger.models import EntityModel

from presentation.forms.account_create_update_form import AccountCreateForm 

class AccountCreateView(LoginRequiredMixin, FormView):
    template_name = 'account_create.html'
    form_class = AccountCreateForm
    success_url = reverse_lazy('accounts:account-create')  # Redirección tras éxito

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        fiscal_profile = self.request.fiscal_profile
        # Pasamos el coa_model requerido por el __init__ de AccountCreateForm
        kwargs['coa_model'] = fiscal_profile.entity.get_coa_model_qs().first()
        return kwargs

    def form_valid(self, form):
        # 1. Recuperar la entidad
        entity = get_object_or_404(
            EntityModel, 
            fiscalprofile__id=self.request.fiscal_profile.id
        )
        try:
            # 2. Invocar el método de creación de la entidad
            entity.create_account(
                code=form.cleaned_data.get('code'),
                name=form.cleaned_data['name'],
                role=form.cleaned_data['role'],
                balance_type=form.cleaned_data['balance_type'],
                active=form.cleaned_data['active']
            )
        except Exception as e:
            form.add_error(None, f"Error en Django Ledger: {e}")
            return self.form_invalid(form)
            
        return super().form_valid(form)