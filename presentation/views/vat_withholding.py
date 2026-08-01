"""Módulo de vistas genéricas basadas en clases para el CRUD de retenciones de IVA."""

from typing import Any
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.vat_withholding import VatWithholdingCertificate
from data_access.models.base import FiscalProfile 
from presentation.forms.vat_withholding import VatWithholdingCertificateForm
from presentation.mixins.requestscopedquerysetmixin import RequestScopedQuerySetMixin

class VatWithholdingCertificateListView(RequestScopedQuerySetMixin, ListView):
    """Vista genérica para listar los Comprobantes de Retención de IVA."""

    model = VatWithholdingCertificate
    template_name = "certificate_list.html"
    context_object_name = "certificates"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Añade la factura asociada al contexto si la vista es contextual."""
        context = super().get_context_data(**kwargs)
        invoice_pk = self.kwargs.get("invoice_pk")
        if invoice_pk:
            context["purchase_invoice"] = get_object_or_404(
                PurchaseLedgerInvoice, pk=invoice_pk
            )
        return context


class VatWithholdingCertificateDetailView(RequestScopedQuerySetMixin, DetailView):
    """Vista genérica para visualizar los detalles de un comprobante de retención."""

    model = VatWithholdingCertificate
    template_name = "certificate_detail.html"
    context_object_name = "certificate"


class VatWithholdingCertificateCreateView(RequestScopedQuerySetMixin, CreateView):
    """Vista para la creación de comprobantes vinculados a una factura obligatoria."""

    model = VatWithholdingCertificate
    form_class = VatWithholdingCertificateForm
    template_name = "certificate_form.html"

    def get_form_kwargs(self) -> dict[str, Any]:
        """Inyecta una instancia inicializada con el contexto de la URL al formulario."""
        kwargs = super().get_form_kwargs()
        
        # Extraemos el invoice de la URL y construimos la instancia base
        invoice_pk = self.kwargs.get("invoice_pk")
        purchase_invoice = get_object_or_404(PurchaseLedgerInvoice, pk=invoice_pk)
        
        # Al pasar esto, el Form tomará esta instancia en lugar de crear una vacía
        kwargs["instance"] = VatWithholdingCertificate(
            purchase_invoice=purchase_invoice,
            fiscal_profile=self.request.user
        )
        return kwargs

    def get_success_url(self) -> str:
        """Retorna la ruta destino al detalle del registro creado."""
        return reverse("vat-withholding-detail", kwargs={"pk": self.object.pk})


class VatWithholdingCertificateUpdateView(RequestScopedQuerySetMixin, UpdateView):
    """Vista para la modificación de comprobantes vinculados a una factura obligatoria."""

    model = VatWithholdingCertificate
    form_class = VatWithholdingCertificateForm
    template_name = "certificate_form.html"

    def get_success_url(self) -> str:
        """Retorna la ruta destino al detalle del registro actualizado."""
        return reverse("vat-withholding-detail", kwargs={"pk": self.object.pk})


class VatWithholdingCertificateDeleteView(RequestScopedQuerySetMixin, DeleteView):
    """Vista genérica para la eliminación física de un comprobante preliminar."""

    model = VatWithholdingCertificate
    template_name = "certificate_confirm_delete.html"
    success_url = reverse_lazy("vat-withholding-list")