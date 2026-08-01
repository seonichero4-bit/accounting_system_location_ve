from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib import messages
from presentation.forms.fiscalperiodselection import FiscalPeriodSelectionForm

class SelectFiscalPeriodView(LoginRequiredMixin, FormView):
    """Vista para seleccionar y persistir el Período Fiscal del Perfil activo."""
    template_name = 'fiscal_period_select.html'
    form_class = FiscalPeriodSelectionForm
    success_url = reverse_lazy('dashboard')  # Ajustar a la ruta principal deseada

    def dispatch(self, request, *args, **kwargs):
        # Valida que exista un Perfil Fiscal activo inyectado por el Middleware
        if not getattr(request, 'fiscal_profile', None):
            messages.warning(request, "Debe seleccionar un Perfil Fiscal activo antes de continuar.")
            return redirect('select_fiscal_profile')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['fiscal_profile'] = self.request.fiscal_profile
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        active_period_id = self.request.session.get('active_fiscal_period_id')
        if active_period_id:
            initial['fiscal_period'] = active_period_id
        return initial

    def form_valid(self, form):
        selected_period = form.cleaned_data['fiscal_period']
        # Persistencia de la clave primaria en la sesión
        self.request.session['active_fiscal_period_id'] = selected_period.pk
        
        display_date = selected_period.subsequent_period or selected_period.start_period
        messages.success(
            self.request,
            f"Período fiscal activo establecido en: {display_date} ({selected_period.get_status_display()})"
        )
        return super().form_valid(form)