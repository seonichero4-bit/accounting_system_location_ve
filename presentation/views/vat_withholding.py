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
            return VatWithholdingCertificate.objects.none()

        queryset = VatWithholdingCertificate.objects.filter(
            fiscal_profile=current_fiscalprofile
        )
        
        invoice_pk = self.kwargs.get("invoice_pk")
        if invoice_pk:
            return queryset.filter(purchase_invoice_id=invoice_pk)
        return queryset


class VatWithholdingCertificateListView(FiscalTenantMixin, ListView):
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


class VatWithholdingCertificateDetailView(FiscalTenantMixin, DetailView):
    """Vista genérica para visualizar los detalles de un comprobante de retención."""

    model = VatWithholdingCertificate
    template_name = "certificate_detail.html"
    context_object_name = "certificate"


class VatWithholdingCertificateCreateView(FiscalTenantMixin, CreateView):
    """Vista para la creación de comprobantes vinculados a una factura obligatoria."""

    model = VatWithholdingCertificate
    form_class = VatWithholdingCertificateForm
    template_name = "certificate_form.html"

    def form_valid(self, form: VatWithholdingCertificateForm):
        """Asigna de manera unívoca la factura y el perfil fiscal al registro."""
        invoice_pk = self.kwargs.get("invoice_pk")
        purchase_invoice = get_object_or_404(PurchaseLedgerInvoice, pk=invoice_pk)
        
        form.instance.purchase_invoice = purchase_invoice
        form.instance.fiscal_profile = self.get_fiscal_profile()
        return super().form_valid(form)

    def get_success_url(self) -> str:
        """Retorna la ruta destino al detalle del registro creado."""
        return reverse("vat-withholding-detail", kwargs={"pk": self.object.pk})


class VatWithholdingCertificateUpdateView(FiscalTenantMixin, UpdateView):
    """Vista para la modificación de comprobantes vinculados a una factura obligatoria."""

    model = VatWithholdingCertificate
    form_class = VatWithholdingCertificateForm
    template_name = "certificate_form.html"

    def get_success_url(self) -> str:
        """Retorna la ruta destino al detalle del registro actualizado."""
        return reverse("vat-withholding-detail", kwargs={"pk": self.object.pk})


class VatWithholdingCertificateDeleteView(FiscalTenantMixin, DeleteView):
    """Vista genérica para la eliminación física de un comprobante preliminar."""

    model = VatWithholdingCertificate
    template_name = "certificate_confirm_delete.html"
    success_url = reverse_lazy("vat-withholding-list")