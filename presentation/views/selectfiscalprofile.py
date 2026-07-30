from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from presentation.forms.fiscalprofileselection import FiscalProfileSelectionForm

class SelectFiscalProfileView(LoginRequiredMixin, FormView):
    template_name = 'fiscal_profile_select.html'
    form_class = FiscalProfileSelectionForm
    success_url = reverse_lazy('dashboard')  # Ajustar a la ruta destino de tu aplicación

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        # Preselecciona el perfil actualmente almacenado en sesión (si existe)
        active_profile_id = self.request.session.get('active_fiscal_profile_id')
        if active_profile_id:
            initial['fiscal_profile'] = active_profile_id
        return initial

    def form_valid(self, form):
        selected_profile = form.cleaned_data['fiscal_profile']
        # Guardar en la sesión la Clave Primaria (ID) del perfil activo
        self.request.session['active_fiscal_profile_id'] = selected_profile.pk
        
        messages.success(
            self.request, 
            f"Perfil fiscal activo cambiado a: {selected_profile.name} ({selected_profile.rif})"
        )
        return super().form_valid(form)