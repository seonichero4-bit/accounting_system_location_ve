"""Suite de pruebas de integración para el CRUD del modelo VatWithholdingCertificate.

Verifica la correcta ejecución de flujos felices y control de errores del ciclo de vida
de los comprobantes de retención de IVA, integrando URL, vistas, formularios y modelos.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.urls import reverse
import pytest

from data_access.models.base import FiscalProfile
from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.vat_withholding import VatWithholdingCertificate
from presentation.forms.vat_withholding import VatWithholdingCertificateForm
from presentation.views.vat_withholding import FiscalTenantMixin


@pytest.mark.django_db
class TestVatWithholdingCertificateCRUD:
    """Clase contenedora de los casos de prueba integrados para el módulo VatWithholding."""

    # =========================================================================
    # 1. Happy Paths (Flujos Felices)
    # =========================================================================

    def test_create_withholding_75_percent_id_hp_001(
        self, client: Any, fiscal_profile: FiscalProfile, purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """[ID_HP_001] Creación de comprobante con retención del 75 %.

        Validar que un comprobante de retención preliminar se crea y calcula
        correctamente con la tasa del 75 % asociada a una factura elegible.
        """
        # Arrange
        url = reverse("vat-withholding-create", kwargs={"invoice_pk": purchase_invoice.pk})
        form_data = {
            "application_date": "2026-07-02",
            "vat_withholding_percentage": 1,  # Corresponde a SETENTA_Y_CINCO
            "document_number": "2026070004"
        }

        # Act
        response = client.post(url, data=form_data)

        # Assert
        assert response.status_code == 302
        certificate = VatWithholdingCertificate.objects.get(purchase_invoice=purchase_invoice)
        assert certificate.vat_withheld_amount == Decimal("75.00")
        assert certificate.status == VatWithholdingCertificate.CertificateStatus.PRELIMINARY

    def test_create_withholding_100_percent_id_hp_002(
        self, client: Any, fiscal_profile: FiscalProfile, supplier: Any
    ) -> None:
        """[ID_HP_002] Creación de comprobante con retención del 100 %.

        Validar que un comprobante de retención preliminar se crea y calcula
        correctamente con la tasa del 100 % asociada a una factura elegible.
        """
        # Arrange
        invoice = PurchaseLedgerInvoice.objects.create(
            fiscal_profile=fiscal_profile,
            supplier=supplier,
            date=date(2026, 7, 1),
            status="PRELIMINARY",
            vat_amount=Decimal("150.00")
        )
        url = reverse("vat-withholding-create", kwargs={"invoice_pk": invoice.pk})
        form_data = {
            "application_date": "2026-07-02",
            "vat_withholding_percentage": 2,  # Corresponde a CIEN
            "document_number": "2026070005"
        }

        # Act
        response = client.post(url, data=form_data)

        # Assert
        assert response.status_code == 302
        certificate = VatWithholdingCertificate.objects.get(purchase_invoice=invoice)
        assert certificate.vat_withheld_amount == Decimal("150.00")

    def test_transition_to_processed_id_hp_003(
        self, fiscal_profile: FiscalProfile, purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """[ID_HP_003] Transición exitosa a estado procesado (PROCESSED).

        Validar que un comprobante en estado preliminar puede cambiar su ciclo
        de vida a procesado para su posterior inmutabilidad.
        """
        # Arrange
        certificate = VatWithholdingCertificate.objects.create(
            fiscal_profile=fiscal_profile,
            purchase_invoice=purchase_invoice,
            application_date=date(2026, 7, 2),
            vat_withholding_percentage=1,
            document_number="2026070001",
            status=VatWithholdingCertificate.CertificateStatus.PRELIMINARY
        )

        # Act
        certificate.status = VatWithholdingCertificate.CertificateStatus.PROCESSED
        certificate.save()

        # Assert
        certificate.refresh_from_db()
        assert certificate.status == VatWithholdingCertificate.CertificateStatus.PROCESSED

    def test_delete_preliminary_certificate_id_hp_004(
        self, client: Any, fiscal_profile: FiscalProfile, purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """[ID_HP_004] Eliminación física de un comprobante preliminar.

        Validar que el sistema permite la remoción de registros de retención de
        IVA que aún no han sido emitidos formalmente.
        """
        # Arrange
        certificate = VatWithholdingCertificate.objects.create(
            fiscal_profile=fiscal_profile,
            purchase_invoice=purchase_invoice,
            application_date=date(2026, 7, 2),
            vat_withholding_percentage=1,
            document_number="2026070001",
            status=VatWithholdingCertificate.CertificateStatus.PRELIMINARY
        )
        url = reverse("vat-withholding-delete", kwargs={"pk": certificate.pk})

        # Act
        response = client.post(url)

        # Assert
        assert response.status_code == 302
        assert not VatWithholdingCertificate.objects.filter(pk=certificate.pk).exists()

    def test_multi_tenant_document_number_isolation_id_hp_005(
        self, client: Any, admin_user: User, purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """[ID_HP_005] Aislamiento multi-inquilino de numeración de comprobantes.

        Verificar que se permite el uso del mismo número de documento de retención
        si pertenecen a perfiles fiscales de inquilinos distintos.
        """
        # Arrange
        profile_b = FiscalProfile.create_profile(
            admin=admin_user,
            entity_name="Empresa B S.A.",
            use_accrual_method=True,
            fy_start_month=1,
            rif="G987654321",
            taxpayer_type="ORDINARY"
        )
        supplier_b = profile_b.create_supplier(name="Proveedor B", rif="E123456789")
        invoice_b = PurchaseLedgerInvoice.objects.create(
            fiscal_profile=profile_b,
            supplier=supplier_b,
            date=date(2026, 7, 1),
            status="PRELIMINARY",
            vat_amount=Decimal("100.00")
        )

        # Creación del primer comprobante para el Perfil A
        url_a = reverse("vat-withholding-create", kwargs={"invoice_pk": purchase_invoice.pk})
        client.post(url_a, {
            "application_date": "2026-07-02",
            "vat_withholding_percentage": 1,
            "document_number": "2026070001"
        })
        cert_a = VatWithholdingCertificate.objects.get(purchase_invoice=purchase_invoice)
        cert_a.document_number = "2026070001"
        cert_a.save()

        # Reemplazo de método en Mixin en tiempo de ejecución (sin mock/patch)
        orig_get_profile = FiscalTenantMixin.get_fiscal_profile
        FiscalTenantMixin.get_fiscal_profile = lambda self: profile_b

        # Act
        try:
            url_b = reverse("vat-withholding-create", kwargs={"invoice_pk": invoice_b.pk})
            response_b = client.post(url_b, {
                "application_date": "2026-07-02",
                "vat_withholding_percentage": 1,
                "document_number": "2026070001"
            })
            cert_b = VatWithholdingCertificate.objects.get(purchase_invoice=invoice_b)
            cert_b.document_number = "2026070001"
            cert_b.save()
        finally:
            FiscalTenantMixin.get_fiscal_profile = orig_get_profile

        # Assert
        assert response_b.status_code == 302
        assert VatWithholdingCertificate.objects.filter(document_number="2026070001").count() == 2

    # =========================================================================
    # 2. Edge Cases (Casos Borde y Manejo de Errores)
    # =========================================================================

    def test_invoice_not_preliminary_raises_validation_error_id_ec_001(
        self, client: Any, fiscal_profile: FiscalProfile, supplier: Any
    ) -> None:
        """[ID_EC_001] Factura asociada no se encuentra en estado preliminar.

        Forzar la creación de un comprobante vinculado a una factura que ya fue
        procesada, registrada o enviada previamente por el sistema.
        """
        # Arrange
        invoice = PurchaseLedgerInvoice.objects.create(
            fiscal_profile=fiscal_profile,
            supplier=supplier,
            date=date(2026, 7, 1),
            status="PROCESSED",
            vat_amount=Decimal("100.00")
        )
        url = reverse("vat-withholding-create", kwargs={"invoice_pk": invoice.pk})
        form_data = {
            "application_date": "2026-07-02",
            "vat_withholding_percentage": 1,
            "document_number": "2026070006"
        }

        # Act
        response = client.post(url, data=form_data)

        # Assert
        assert response.status_code == 200
        form = response.context["form"]
        assert "purchase_invoice" in form.errors
        assert form.errors["purchase_invoice"] == ["La factura asociada ya fue procesada."]

    def test_invoice_vat_zero_or_negative_raises_validation_error_id_ec_002(
        self, client: Any, fiscal_profile: FiscalProfile, supplier: Any
    ) -> None:
        """[ID_EC_002] Factura asociada posee IVA igual o menor a cero.

        Evitar la emisión de comprobantes de retención para facturas de compra
        exentas o con cálculos de IVA inválidos.
        """
        # Arrange
        invoice = PurchaseLedgerInvoice.objects.create(
            fiscal_profile=fiscal_profile,
            supplier=supplier,
            date=date(2026, 7, 1),
            status="PRELIMINARY",
            vat_amount=Decimal("0.00")
        )
        url = reverse("vat-withholding-create", kwargs={"invoice_pk": invoice.pk})
        form_data = {
            "application_date": "2026-07-02",
            "vat_withholding_percentage": 1,
            "document_number": "2026070007"
        }

        # Act
        response = client.post(url, data=form_data)

        # Assert
        assert response.status_code == 200
        form = response.context["form"]
        assert "purchase_invoice" in form.errors
        assert form.errors["purchase_invoice"] == [
            "El IVA de la factura asociada debe ser estrictamente mayor a cero."
        ]

    def test_application_date_before_invoice_date_raises_validation_error_id_ec_003(
        self, client: Any, fiscal_profile: FiscalProfile, purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """[ID_EC_003] Fecha de aplicación anterior a la de emisión de la factura.

        Validar la coherencia cronológica fiscal impidiendo que un comprobante
        se aplique antes de que exista la factura de compra de origen.
        """
        # Arrange
        url = reverse("vat-withholding-create", kwargs={"invoice_pk": purchase_invoice.pk})
        form_data = {
            "application_date": "2026-06-30",  # Anterior al 2026-07-01 de la factura
            "vat_withholding_percentage": 1,
            "document_number": "2026070008"
        }

        # Act
        response = client.post(url, data=form_data)

        # Assert
        assert response.status_code == 200
        form = response.context["form"]
        assert "application_date" in form.errors
        assert form.errors["application_date"] == [
            "La fecha de aplicación no puede ser menor a la fecha de emisión de la factura asociada."
        ]

    def test_application_date_future_raises_integrity_error_id_ec_004(
        self, fiscal_profile: FiscalProfile, purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """[ID_EC_004] Fecha de aplicación configurada en el futuro."""
        # Arrange
        cert = VatWithholdingCertificate(
            fiscal_profile=fiscal_profile,
            purchase_invoice=purchase_invoice,
            application_date=date(2026, 12, 31),  # Fecha futura en el año corriente
            vat_withholding_percentage=1,
            document_number="2026120009"
        )

        # Act & Assert: Validación directa de restricción SQL omitiendo capa HTTP
        with pytest.raises(IntegrityError):
            cert.save()

    def test_duplicate_document_number_same_profile_raises_integrity_error_id_ec_005(
        self, client: Any, fiscal_profile: FiscalProfile, purchase_invoice: PurchaseLedgerInvoice, supplier: Any
    ) -> None:
        """[ID_EC_005] Duplicidad de número de documento bajo el mismo perfil fiscal."""
        # Arrange
        VatWithholdingCertificate.objects.create(
            fiscal_profile=fiscal_profile,
            purchase_invoice=purchase_invoice,
            application_date=date(2026, 7, 2),
            vat_withholding_percentage=1,
            document_number="2026070002",
            status=VatWithholdingCertificate.CertificateStatus.PRELIMINARY
        )

        invoice_2 = PurchaseLedgerInvoice.objects.create(
            fiscal_profile=fiscal_profile,
            supplier=supplier,
            date=date(2026, 7, 1),
            number="FACT-00002",
            invoice_control="CTRL-00002",
            status="PRELIMINARY",
            vat_amount=Decimal("100.00")
        )

        # Act & Assert: Evitamos client.post para validar directamente la restricción SQL
        cert_2 = VatWithholdingCertificate(
            fiscal_profile=fiscal_profile,
            purchase_invoice=invoice_2,
            application_date=date(2026, 7, 2),
            vat_withholding_percentage=1,
            document_number="2026070002"
        )
        
        with pytest.raises(IntegrityError):
            cert_2.save()

    def test_inconsistent_document_number_prefix_raises_validation_error_id_ec_006(
        self, client: Any, fiscal_profile: FiscalProfile, purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """[ID_EC_006] Inconsistencia de prefijo de número de documento vs fecha de aplicación."""
        # Arrange - Fecha en el tiempo presente relativo a la ejecución para saltar el CheckConstraint
        certificate = VatWithholdingCertificate.objects.create(
            fiscal_profile=fiscal_profile,
            purchase_invoice=purchase_invoice,
            application_date=date(2026, 7, 15),
            vat_withholding_percentage=1,
            document_number="2026070001",  # Prefijo coherente con Julio 2026
            status="PRELIMINARY"
        )
        url = reverse("vat-withholding-update", kwargs={
            "invoice_pk": purchase_invoice.pk,
            "pk": certificate.pk
        })
        form_data = {
            "application_date": "2026-07-15",  # Mes de Julio (202607)
            "vat_withholding_percentage": 1,
            "document_number": "2026010002"    # Prefijo incoherente (202601) para forzar error de negocio
        }

        # Act
        response = client.post(url, data=form_data)

        # Assert
        assert response.status_code == 200
        form = response.context["form"]
        assert "document_number" in form.errors

    def test_modify_processed_certificate_raises_validation_error_id_ec_007(
        self, client: Any, fiscal_profile: FiscalProfile, purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """[ID_EC_007] Intento de modificación sobre un comprobante procesado (PROCESSED)."""
        # Arrange
        certificate = VatWithholdingCertificate.objects.create(
            fiscal_profile=fiscal_profile,
            purchase_invoice=purchase_invoice,
            application_date=date(2026, 7, 2),
            vat_withholding_percentage=1,
            document_number="2026070001",
            status=VatWithholdingCertificate.CertificateStatus.PROCESSED
        )
        url = reverse("vat-withholding-update", kwargs={
            "invoice_pk": purchase_invoice.pk,
            "pk": certificate.pk
        })
        form_data = {
            "application_date": "2026-07-03",
            "vat_withholding_percentage": 2,
            "document_number": "2026070002"  # Prefijo corregido de 202604 a 202607
        }

        # Act & Assert
        with pytest.raises(ValidationError) as excinfo:
            client.post(url, data=form_data)
        assert "Este comprobante de retención ya ha sido procesado y es estrictamente de solo lectura." in str(excinfo.value)

    def test_delete_processed_certificate_raises_validation_error_id_ec_008(
        self, client: Any, fiscal_profile: FiscalProfile, purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """[ID_EC_008] Intento de eliminación física sobre un comprobante procesado.

        Validar la protección legal del histórico transaccional que impide la remoción
        de comprobantes procesados del sistema.
        """
        # Arrange
        certificate = VatWithholdingCertificate.objects.create(
            fiscal_profile=fiscal_profile,
            purchase_invoice=purchase_invoice,
            application_date=date(2026, 7, 2),
            vat_withholding_percentage=1,
            document_number="2026070001",
            status=VatWithholdingCertificate.CertificateStatus.PROCESSED
        )
        url = reverse("vat-withholding-delete", kwargs={"pk": certificate.pk})

        # Act & Assert
        with pytest.raises(ValidationError) as excinfo:
            client.post(url)
        assert "Los comprobantes emitidos y procesados no pueden ser eliminados del sistema por razones legales." in str(excinfo.value)

    def test_delete_invoice_protected_raises_protected_error_id_ec_009(
        self, client: Any, fiscal_profile: FiscalProfile, purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """[ID_EC_009] Integridad referencial por eliminación de factura de compra asociada.

        Validar que una factura de compra no puede ser eliminada físicamente si tiene
        un comprobante de retención enlazado de manera unívoca.
        """
        # Arrange
        VatWithholdingCertificate.objects.create(
            fiscal_profile=fiscal_profile,
            purchase_invoice=purchase_invoice,
            application_date=date(2026, 7, 2),
            vat_withholding_percentage=1,
            document_number="2026070001",
            status="PRELIMINARY"
        )
        url = reverse("purchase-invoice-delete", kwargs={"pk": purchase_invoice.pk})

        # Act & Assert
        with pytest.raises(ProtectedError):
            client.post(url)

    def test_invalid_withholding_percentage_db_constraint_id_ec_010(
        self, fiscal_profile: FiscalProfile, purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """[ID_EC_010] Porcentaje de retención fuera de los límites fiscales definidos.

        Asegurar que valores de porcentaje inválidos inyectados a nivel de base de
        datos o por bypass de formularios sean rechazados por integridad.
        """
            # Arrange
        cert = VatWithholdingCertificate(
            fiscal_profile=fiscal_profile,
            purchase_invoice=purchase_invoice,
            application_date=date(2026, 7, 2),
            vat_withholding_percentage=3,  # Valor no permitido por choices e integridad
            document_number="2026070003",
            status="PRELIMINARY"
        )

        # Act & Assert
        with pytest.raises(ValueError):
            cert.save()