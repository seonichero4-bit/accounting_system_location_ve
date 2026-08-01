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
from ..mixins.requestscopedquerysetmixin import RequestScopedQuerySetMixin 


class IslrWithholdingCertificateListView(RequestScopedQuerySetMixin, ListView):
    """Vista genérica para listar los comprobantes de retención de ISLR."""

    model = IslrWithholdingCertificate
    template_name = "certificate_list.html"
    context_object_name = "certificates"


class IslrWithholdingCertificateDetailView(RequestScopedQuerySetMixin, DetailView):
    """Vista genérica para visualizar el detalle de un comprobante."""

    model = IslrWithholdingCertificate
    template_name = "certificate_detail.html"
    context_object_name = "certificate"


class IslrWithholdingCertificateCreateView(RequestScopedQuerySetMixin, CreateView):
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
            fiscal_profile=self.request.fiscal_profile
        )
        return kwargs

    def get_success_url(self) -> str:
        """Define la ruta de redirección al detalle tras guardar exitosamente."""
        return reverse("islr-withholding-detail", kwargs={"pk": self.object.pk})


class IslrWithholdingCertificateUpdateView(RequestScopedQuerySetMixin, UpdateView):
    """Vista contextual para la edición de comprobantes de retención de ISLR."""

    model = IslrWithholdingCertificate
    form_class = IslrWithholdingCertificateForm
    template_name = "certificate_form.html"

    def get_success_url(self) -> str:
        """Define la ruta de redirección al detalle tras la actualización."""
        return reverse("islr-withholding-detail", kwargs={"pk": self.object.pk})


class IslrWithholdingCertificateDeleteView(RequestScopedQuerySetMixin, DeleteView):
    """Vista genérica para procesar la eliminación de un comprobante."""

    model = IslrWithholdingCertificate
    template_name = "certificate_confirm_delete.html"
    success_url = reverse_lazy("islr-withholding-list")