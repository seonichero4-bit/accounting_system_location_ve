"""Módulo de presentación para la gestión de retenciones de ISLR.

Define el formulario basado en ModelForm y las vistas genéricas del CRUD
para el modelo IslrWithholdingCertificate, aplicando aislamiento multi-tenant.
"""

from typing import Any
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from presentation.forms.islr_withholding import IslrWithholdingCertificateForm
from data_access.models.base import FiscalProfile
from data_access.models.islr_withholding import IslrWithholdingCertificate
from data_access.models.purchase_book import PurchaseLedgerInvoice


class FiscalTenantMixin:
    """Mixin base para inyectar y aislar el perfil fiscal activo en las vistas."""

    def get_fiscal_profile(self) -> FiscalProfile:
        """Obtiene el perfil fiscal del inquilino actual.

        Nota: En producción, esto debe derivarse de `self.request.user.entity.fiscal_profile`
        o del middleware activo. Por simplicidad del CRUD, retorna el primero disponible.
        """
        return FiscalProfile.objects.first()

    def get_queryset(self) -> QuerySet:
        """Aísla las consultas al perfil fiscal activo y filtra por factura si aplica."""
        current_fiscalprofile = self.get_fiscal_profile()

        if current_fiscalprofile is None:
            return IslrWithholdingCertificate.objects.none()

        queryset = IslrWithholdingCertificate.objects.filter(
            fiscal_profile=current_fiscalprofile
        )

        invoice_pk = self.kwargs.get("invoice_pk")
        if invoice_pk:
            return queryset.filter(purchase_invoice_id=invoice_pk)
        return queryset

class IslrWithholdingCertificateListView(FiscalTenantMixin, ListView):
    """Vista genérica para listar los comprobantes de retención de ISLR."""

    model = IslrWithholdingCertificate
    template_name = "certificate_list.html"
    context_object_name = "certificates"


class IslrWithholdingCertificateDetailView(FiscalTenantMixin, DetailView):
    """Vista genérica para visualizar el detalle de un comprobante."""

    model = IslrWithholdingCertificate
    template_name = "certificate_detail.html"
    context_object_name = "certificate"


class IslrWithholdingCertificateCreateView(FiscalTenantMixin, CreateView):
    """Vista contextual para la creación de comprobantes de retención de ISLR.

    Obliga el flujo desde una factura de compra específica provista en la URL.
    """

    model = IslrWithholdingCertificate
    form_class = IslrWithholdingCertificateForm
    template_name = "certificate_form.html"

    def get_form_kwargs(self) -> dict[str, Any]:
        """Inyecta una instancia inicializada con el contexto de la URL al formulario."""
        kwargs = super().get_form_kwargs()
        
        # Extraemos el invoice de la URL y construimos la instancia base
        invoice_pk = self.kwargs.get("invoice_pk")
        purchase_invoice = get_object_or_404(PurchaseLedgerInvoice, pk=invoice_pk)
        
        # Al pasar esto, el Form tomará esta instancia en lugar de crear una vacía
        kwargs["instance"] = IslrWithholdingCertificate(
            purchase_invoice=purchase_invoice,
            fiscal_profile=self.get_fiscal_profile()
        )
        return kwargs


    # def form_valid(self, form: IslrWithholdingCertificateForm) -> HttpResponseRedirect:
    #     """Asigna el perfil fiscal y la factura contextual antes del commit final."""
    #     invoice_pk = self.kwargs.get("invoice_pk")
    #     if not invoice_pk:
    #         form.add_error(None, "La transacción requiere una factura de compra contextual.")
    #         return self.form_invalid(form)

    #     fiscal_profile = self.get_fiscal_profile()
    #     try:
    #         purchase_invoice = PurchaseLedgerInvoice.objects.get(
    #             pk=invoice_pk, fiscal_profile=fiscal_profile
    #         )
    #     except PurchaseLedgerInvoice.DoesNotExist:
    #         form.add_error(
    #             None, "La factura indicada no existe o no pertenece a este perfil fiscal."
    #         )
    #         return self.form_invalid(form)

    #     form.instance.fiscal_profile = fiscal_profile
    #     form.instance.purchase_invoice = purchase_invoice
    #     return super().form_valid(form)

    def get_success_url(self) -> str:
        """Define la ruta de redirección al detalle tras guardar exitosamente."""
        return reverse("islr-withholding-detail", kwargs={"pk": self.object.pk})


class IslrWithholdingCertificateUpdateView(FiscalTenantMixin, UpdateView):
    """Vista contextual para la edición de comprobantes de retención de ISLR."""

    model = IslrWithholdingCertificate
    form_class = IslrWithholdingCertificateForm
    template_name = "certificate_form.html"

    def get_success_url(self) -> str:
        """Define la ruta de redirección al detalle tras la actualización."""
        return reverse("islr-withholding-detail", kwargs={"pk": self.object.pk})


class IslrWithholdingCertificateDeleteView(FiscalTenantMixin, DeleteView):
    """Vista genérica para procesar la eliminación de un comprobante."""

    model = IslrWithholdingCertificate
    template_name = "certificate_confirm_delete.html"
    success_url = reverse_lazy("islr-withholding-list")