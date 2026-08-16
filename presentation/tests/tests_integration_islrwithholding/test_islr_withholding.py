"""Suite de pruebas de integración para el modelo IslrWithholdingCertificate.

Valida la interacción entre el cliente HTTP, las vistas contextuales y el 
modelo de datos asegurando persistencia, validaciones y reglas multi-tenant.
"""

import pytest
from django.urls import reverse
from django.core.exceptions import ValidationError

from data_access.models.islr_withholding import IslrWithholdingCertificate


@pytest.mark.django_db
class TestIslrWithholdingCertificateIntegration:
    """Pruebas de integración para el ciclo de vida del comprobante de ISLR."""

    def test_ID_HP_001_create_certificate_via_view(self, logged_client, preliminary_invoice):
        """Valida la creación exitosa de un comprobante desde la vista contextual."""
        # Arrange
        url = reverse("islr-withholding-create", kwargs={"invoice_pk": preliminary_invoice.pk})
        form_data = {
            "document_number": "2026080001",
            "application_date": "2026-08-10",
            "concepts_payment_pnr": 1,
        }

        # Act
        response = logged_client.post(url, data=form_data)

        # Assert
        assert response.status_code == 302
        assert IslrWithholdingCertificate.objects.count() == 1
        certificate = IslrWithholdingCertificate.objects.first()
        assert certificate.document_number == "2026080001"
        assert response.url == reverse("invoice-islr-withholding-detail", kwargs={
            "invoice_pk": preliminary_invoice.pk,
            "pk": certificate.pk
        })

    def test_ID_HP_002_update_preliminary_certificate_via_view(
        self, logged_client, preliminary_invoice
    ):
        """Valida la actualización de un comprobante preliminar mediante la vista de edición."""
        # Arrange
        certificate = IslrWithholdingCertificate.objects.create(
            purchase_invoice=preliminary_invoice,
            document_number="2026080001",
            application_date="2026-1-3",
            fiscal_profile=preliminary_invoice.fiscal_profile,
            fiscal_period="2026-1-1",
            concepts_payment_pnr=1,
            islr_withheld_amount="0.00",
            subtracting="0.00",
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
        )
        url = reverse("islr-withholding-update", kwargs={
            "invoice_pk": preliminary_invoice.pk,
            "pk": certificate.pk
        })
        form_data = {
            "document_number": "2026080002",
            "application_date": "2026-08-15",
            "concepts_payment_pjd": 1,
        }

        # Act
        response = logged_client.post(url, data=form_data)

        # Assert
        assert response.status_code == 302
        certificate.refresh_from_db()
        assert certificate.document_number == "2026080002"
        assert str(certificate.application_date) == "2026-08-15"

    def test_ID_HP_003_contextual_isolation_detail_view(
        self, other_logged_client, processed_islr_certificate
    ):
        """Asegura que comprobantes de un perfil fiscal no sean accesibles por otro."""
        # Arrange
        invoice_pk = processed_islr_certificate.purchase_invoice.pk
        url = reverse("invoice-islr-withholding-detail", kwargs={
            "invoice_pk": invoice_pk,
            "pk": processed_islr_certificate.pk
        })

        # Act
        response = other_logged_client.get(url)

        # Assert
        assert response.status_code == 404

    def test_ID_EC_001_model_validation_error_caught_in_view(self, logged_client, preliminary_invoice):
        """Verifica que la vista capture y muestre errores de validación del modelo."""
        # Arrange
        url = reverse("islr-withholding-create", kwargs={"invoice_pk": preliminary_invoice.pk})
        form_data = {
            "document_number": "2026070001",
            "application_date": "2026-07-31",  # Retroactiva: Menor a factura (2026-08-01)
            "concepts_payment_pnr": 1,
        }

        # Act
        response = logged_client.post(url, data=form_data)

        # Assert
        assert response.status_code == 200
        assert "application_date" in response.context["form"].errors
        assert IslrWithholdingCertificate.objects.count() == 0

    def test_ID_EC_002_integrity_error_duplicate_correlative_caught_in_view(
        self, logged_client, processed_islr_certificate, alternative_preliminary_invoice
    ):
        """Verifica que la vista intercepte violaciones de unicidad en base de datos."""
        # Arrange
        invoice = alternative_preliminary_invoice
        url = reverse("islr-withholding-create", kwargs={"invoice_pk": invoice.pk})
        form_data = {
            "document_number": processed_islr_certificate.document_number,  # Duplicado
            "application_date": "2026-08-15",
            "concepts_payment_pnr": 1,
        }

        # Act
        response = logged_client.post(url, data=form_data)

        # Assert
        assert response.status_code == 200
        assert "document_number" in response.context["form"].errors

    def test_ID_EC_004_delete_processed_certificate_raises_validation_error(
        self, logged_client, alternative_processed_islr_certificate
    ):
        """Verifica que intentar eliminar un registro procesado retorne un error en el formulario."""
        # Arrange
        invoice_pk = alternative_processed_islr_certificate.purchase_invoice.pk
        url = reverse("invoice-islr-withholding-delete", kwargs={
            "invoice_pk": invoice_pk,
            "pk": alternative_processed_islr_certificate.pk
        })

        # Act
        response = logged_client.post(url)

        # Assert
        #assert response.status_code == 200
        assert response.context["form"].errors

    def test_ID_EC_004_delete_processed_certificate_model_raises(
        self, processed_islr_certificate
    ):
        """Prueba estricta a nivel de modelo para asegurar el lanzamiento de la excepción."""
        # Arrange
        # El certificado ya está en estado PROCESSED (setup de fixture)

        # Act & Assert
        with pytest.raises(ValidationError):
            processed_islr_certificate.delete()

    def test_ID_EC_005_create_view_invalid_invoice_pk_returns_404(self, logged_client):
        """Comprueba que proveer un ID de factura inexistente retorne HTTP 404."""
        # Arrange
        url = reverse("islr-withholding-create", kwargs={"invoice_pk": 9999})

        # Act
        response = logged_client.get(url)

        # Assert
        assert response.status_code == 404