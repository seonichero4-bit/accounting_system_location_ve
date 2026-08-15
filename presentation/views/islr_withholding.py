"""Módulo de presentación para la gestión de retenciones de ISLR.

Define el formulario basado en ModelForm y las vistas genéricas del CRUD
para el modelo IslrWithholdingCertificate, aplicando aislamiento multi-tenant
y manejo de excepciones de modelo y base de datos.
"""

from typing import Any
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
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

from ..utils import unwrap_lazy_object
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
        
        # Extraemos el datetime.date real envuelto en el SimpleLazyObject
        fiscal_period_date = unwrap_lazy_object(getattr(self.request, "fiscal_period", None))
        fiscal_profile_obj = unwrap_lazy_object(getattr(self.request, "fiscal_profile", None))

        kwargs["instance"] = IslrWithholdingCertificate(
            purchase_invoice=purchase_invoice,
            fiscal_profile=fiscal_profile_obj,
            fiscal_period=fiscal_period_date)
        return kwargs

    def form_valid(self, form: Any) -> HttpResponse:
        """Procesa el guardado capturando validaciones de save() y restricciones DB."""
        try:
            return super().form_valid(form)
        except ValidationError as e:
            if hasattr(e, "error_dict"):
                for field, errors in e.error_dict.items():
                    form.add_error(None if field == "__all__" else field, errors)
            else:
                form.add_error(None, e)
            return self.form_invalid(form)
        except IntegrityError as e:
            err_msg = str(e)
            if "unique_document_per_fiscal_profile" in err_msg or "document_number" in err_msg:
                form.add_error(
                    "document_number",
                    "Ya existe un comprobante con este número de documento para el perfil fiscal actual."
                )
            else:
                form.add_error(
                    None,
                    "Error de integridad en la base de datos al guardar el comprobante."
                )
            return self.form_invalid(form)

    def get_success_url(self) -> str:
        """Define la ruta de redirección al detalle tras guardar exitosamente."""
        return reverse("islr-withholding-detail", kwargs={"pk": self.object.pk})


class IslrWithholdingCertificateUpdateView(RequestScopedQuerySetMixin, UpdateView):
    """Vista contextual para la edición de comprobantes de retención de ISLR."""

    model = IslrWithholdingCertificate
    form_class = IslrWithholdingCertificateForm
    template_name = "certificate_form.html"

    def form_valid(self, form: Any) -> HttpResponse:
        """Procesa la actualización capturando bloqueos de modificación y restricciones DB."""
        try:
            return super().form_valid(form)
        except ValidationError as e:
            if hasattr(e, "error_dict"):
                for field, errors in e.error_dict.items():
                    form.add_error(None if field == "__all__" else field, errors)
            else:
                form.add_error(None, e)
            return self.form_invalid(form)
        except IntegrityError as e:
            err_msg = str(e)
            if "unique_document_per_fiscal_profile" in err_msg or "document_number" in err_msg:
                form.add_error(
                    "document_number",
                    "Ya existe un comprobante con este número de documento para el perfil fiscal actual."
                )
            else:
                form.add_error(
                    None,
                    "Error de integridad en la base de datos al actualizar el comprobante."
                )
            return self.form_invalid(form)

    def get_success_url(self) -> str:
        """Define la ruta de redirección al detalle tras la actualización."""
        return reverse("islr-withholding-detail", kwargs={"pk": self.object.pk})


class IslrWithholdingCertificateDeleteView(RequestScopedQuerySetMixin, DeleteView):
    """Vista genérica para procesar la eliminación de un comprobante."""

    model = IslrWithholdingCertificate
    template_name = "certificate_confirm_delete.html"
    success_url = reverse_lazy("islr-withholding-list")

    def form_valid(self, form: Any) -> HttpResponse:
        """Maneja la eliminación basada en formularios (Django 4.0+)."""
        try:
            return super().form_valid(form)
        except ValidationError as e:
            if hasattr(e, "error_dict"):
                for field, errors in e.error_dict.items():
                    form.add_error(None if field == "__all__" else field, errors)
            else:
                form.add_error(None, e)
            return self.form_invalid(form)
        except ProtectedError:
            form.add_error(
                None,
                "No se puede eliminar este comprobante porque posee registros asociados protegidos."
            )
            return self.form_invalid(form)
        except IntegrityError:
            form.add_error(
                None,
                "Error de integridad en la base de datos al intentar eliminar el comprobante."
            )
            return self.form_invalid(form)
