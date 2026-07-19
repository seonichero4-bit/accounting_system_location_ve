"""Suite de pruebas de integración para el ciclo de vida y CRUD de IslrWithholdingCertificate.

Valida cálculos impositivos complejos bajo regulaciones del SENIAT, exclusión mutua,
restricciones de inmutabilidad y aislamiento multi-tenant estricto.
"""

from datetime import date
from typing import Any
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse

from data_access.models.concep_payment_islr.concepts_payment_pjd import IslrPjdChoices
from data_access.models.concep_payment_islr.concepts_payment_pjnd import IslrPjndChoices
from data_access.models.concep_payment_islr.concepts_payment_pnnr import IslrPnnrChoices
from data_access.models.concep_payment_islr.concepts_payment_pnr import IslrPnrChoices
from data_access.models.base import FiscalProfile
from data_access.models.islr_withholding import IslrWithholdingCertificate
from data_access.models.purchase_book import PurchaseLedgerInvoice


@pytest.mark.django_db
class TestIslrWithholdingCertificateCrud:
    """Encapsula los escenarios Happy Paths y Edge Cases para el modelo de retenciones."""

    # =========================================================================
    # HAPPY PATHS (FLUJOS FELICES)
    # =========================================================================

    def test_create_certificate_pnnr_calculation_success_ID_HP_001(
        self, 
        tenant_profile: FiscalProfile, 
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Valida el cálculo de retención automática para Personas Naturales No Residentes."""
        # Arrange
        preliminary_purchase_invoice.taxable_base = Decimal("1000.00")
        preliminary_purchase_invoice.subtotal = Decimal("1000.00")
        preliminary_purchase_invoice.save()

        # Act
        certificate = IslrWithholdingCertificate.objects.create(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700001",
            application_date=date(2026, 7, 18),
            concepts_payment_pnnr=IslrPnnrChoices.HONORARIOS_PROFESIONALES,
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
        )

        # Assert
        # Honorarios Profesionales PNNR: Base Imponible = 90%, Alícuota = 34%. (1000 * 0.90 * 0.34) = 306.00
        assert certificate.pk is not None
        assert certificate.islr_withheld_amount == Decimal("306.00")
        assert certificate.subtracting == Decimal("0.00")

    def test_create_certificate_pnr_over_threshold_success_ID_HP_002(
        self, 
        tenant_profile: FiscalProfile, 
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Valida la aplicación del sustraendo legal y retención neta sobre el umbral mínimo."""
        # Arrange
        # Configuración para superar el factor fijo (83.3334 UT * 150 = 12500.01)
        preliminary_purchase_invoice.taxable_base = Decimal("20000.00")
        preliminary_purchase_invoice.subtotal = Decimal("20000.00")
        preliminary_purchase_invoice.save()

        # Act
        certificate = IslrWithholdingCertificate.objects.create(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700002",
            application_date=date(2026, 7, 18),
            concepts_payment_pnr=IslrPnrChoices.HONORARIOS_PROFESIONALES,
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
        )

        # Assert
        # PNR Honorarios: Base = 100%, Alícuota = 3%, Sustraendo Activo. 
        # Sustraendo = 83.3334 * 150 * 0.03 = 375.00. Retención bruta = 20000 * 0.03 = 600.00. Neta = 225.00
        assert certificate.subtracting == Decimal("375.00")
        assert certificate.islr_withheld_amount == Decimal("225.00")

    def test_create_certificate_pjnd_tarifa_dos_success_ID_HP_003(
        self, 
        tenant_profile: FiscalProfile, 
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Verifica la correcta aplicación del tramo superior en la matriz progresiva Tarifa N° 2."""
        # Arrange
        # Monto alto para forzar tramo > 3000 UT. Base = 600000 * 0.90 = 540000 Bs / 150 = 3600 UT.
        preliminary_purchase_invoice.taxable_base = Decimal("600000.00")
        preliminary_purchase_invoice.subtotal = Decimal("600000.00")
        preliminary_purchase_invoice.save()

        # Act
        certificate = IslrWithholdingCertificate.objects.create(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700003",
            application_date=date(2026, 7, 18),
            concepts_payment_pjnd=IslrPjndChoices.HONORARIOS_PROFESIONALES,
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
        )

        # Assert
        # Tramo > 3000 UT aplica Alícuota de 34% y Sustraendo de 500 UT (500 * 150 = 75000)
        # (540000 * 0.34) - 75000 = 183600 - 75000 = 108600.00
        assert certificate.islr_withheld_amount == Decimal("108600.00")

    def test_create_certificate_pjd_linear_calculation_success_ID_HP_004(
        self, 
        tenant_profile: FiscalProfile, 
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Comprueba el flujo ordinario lineal directo para personas jurídicas domiciliadas."""
        # Arrange
        preliminary_purchase_invoice.taxable_base = Decimal("5000.00")
        preliminary_purchase_invoice.subtotal = Decimal("5000.00")
        preliminary_purchase_invoice.save()

        # Act
        certificate = IslrWithholdingCertificate.objects.create(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700004",
            application_date=date(2026, 7, 18),
            concepts_payment_pjd=IslrPjdChoices.HONORARIOS_PROFESIONALES,
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
        )

        # Assert
        # PJD Honorarios: Base = 100%, Alícuota = 5%. 5000 * 0.05 = 250.00
        assert certificate.islr_withheld_amount == Decimal("250.00")

    def test_multi_tenant_isolation_reading_and_filtering_ID_HP_005(
        self, 
        client: Client, 
        tenant_profile: FiscalProfile, 
        secondary_tenant_profile: FiscalProfile,
        preliminary_purchase_invoice: PurchaseLedgerInvoice,
        secondary_local_supplier: Any
    ) -> None:
        """Garantiza que las consultas de listados aíslen estrictamente los registros por inquilino."""
        # Arrange
        # Comprobante del inquilino primario activo
        certificate_tenant_one = IslrWithholdingCertificate.objects.create(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700001",
            application_date=date(2026, 7, 18),
            concepts_payment_pjd=IslrPjdChoices.SERVICIOS,
        )

        # Factura e Involucrados para el inquilino secundario aislado
        invoice_tenant_two = PurchaseLedgerInvoice.objects.create(
            fiscal_profile=secondary_tenant_profile,
            supplier=secondary_local_supplier,
            number="FACT-TENANT-2",
            invoice_control="CTRL-T2",
            document_type=PurchaseLedgerInvoice.DocumentType.INVOICE,
            purchase_type=PurchaseLedgerInvoice.PurchaseType.INTERNAL,
            date=date(2026, 7, 12),
            application_month_year="07-2026",
            taxable_base=Decimal("1000.00"),
            exempt_amount=Decimal("0.00"),
            subtotal=Decimal("1000.00"),
            vat_percentage=PurchaseLedgerInvoice.VatPercentageChoices.GENERAL,
            vat_amount=Decimal("160.00"),
            total_purchase=Decimal("1160.00"),
        )
        certificate_tenant_two = IslrWithholdingCertificate.objects.create(
            fiscal_profile=secondary_tenant_profile,
            purchase_invoice=invoice_tenant_two,
            document_number="20260700099",
            application_date=date(2026, 7, 18),
            concepts_payment_pjd=IslrPjdChoices.SERVICIOS,
        )

        # Act
        # El mixin asume el perfil del primer registro disponible en la base de datos (Inquilino 1)
        response = client.get(reverse("islr-withholding-list"))

        # Assert
        assert response.status_code == 200
        certificates_context = response.context["certificates"]
        assert certificate_tenant_one in certificates_context
        assert certificate_tenant_two not in certificates_context

    def test_update_certificate_preliminary_recalculates_successfully_ID_HP_006(
        self, 
        client: Client, 
        tenant_profile: FiscalProfile, 
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Verifica la modificación de registros preliminares disparando el recálculo automático."""
        # Arrange
        certificate = IslrWithholdingCertificate.objects.create(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700006",
            application_date=date(2026, 7, 18),
            concepts_payment_pjd=IslrPjdChoices.HONORARIOS_PROFESIONALES,  # Alícuota 5% -> 50.00
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
        )
        url = reverse("islr-withholding-update", kwargs={"invoice_pk": preliminary_purchase_invoice.pk, "pk": certificate.pk})
        form_data = {
            "document_number": "20260700006",
            "application_date": "2026-07-18",
            "concepts_payment_pjd": IslrPjdChoices.SERVICIOS,  # Cambia a Servicios -> Alícuota 2%
        }

        # Act
        response = client.post(url, data=form_data)

        # Assert
        certificate.refresh_from_db()
        assert response.status_code == 302
        assert certificate.concepts_payment_pjd == IslrPjdChoices.SERVICIOS
        assert certificate.islr_withheld_amount == Decimal("20.00")  # 1000.00 * 0.02 = 20.00

    def test_delete_certificate_preliminary_removes_from_db_ID_HP_007(
        self, 
        client: Client, 
        tenant_profile: FiscalProfile, 
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Comprueba la remoción física de registros en estado preliminar."""
        # Arrange
        certificate = IslrWithholdingCertificate.objects.create(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700007",
            application_date=date(2026, 7, 18),
            concepts_payment_pjd=IslrPjdChoices.HONORARIOS_PROFESIONALES,
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
        )
        url = reverse("islr-withholding-delete", kwargs={"pk": certificate.pk})

        # Act
        response = client.post(url)

        # Assert
        assert response.status_code == 302
        assert not IslrWithholdingCertificate.objects.filter(pk=certificate.pk).exists()

    # =========================================================================
    # EDGE CASES (CASOS BORDE Y MANEJO DE ERRORES)
    # =========================================================================

    def test_missing_all_islr_concepts_raises_validation_error_ID_EC_001(
        self, 
        tenant_profile: FiscalProfile, 
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Evalúa el rechazo de guardado al omitir clasificaciones jurídicas."""
        # Arrange
        certificate = IslrWithholdingCertificate(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700010",
            application_date=date(2026, 7, 18),
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.clean()
        assert "missing_islr_concept" in exc_info.value.code

    def test_multiple_simultaneous_concepts_raises_validation_error_ID_EC_002(
        self, 
        tenant_profile: FiscalProfile, 
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Garantiza el cumplimiento de exclusividad mutua de conceptos."""
        # Arrange
        certificate = IslrWithholdingCertificate(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700011",
            application_date=date(2026, 7, 18),
            concepts_payment_pnr=IslrPnrChoices.HONORARIOS_PROFESIONALES,
            concepts_payment_pjd=IslrPjdChoices.HONORARIOS_PROFESIONALES,
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.clean()
        assert "multiple_islr_concepts" in exc_info.value.code

    def test_invoice_not_preliminary_raises_validation_error_ID_EC_003(
        self,
        tenant_profile: FiscalProfile,
        processed_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Impide generar certificados sobre facturas ya procesadas o cerradas."""
        # Arrange
        certificate = IslrWithholdingCertificate(
            fiscal_profile=tenant_profile,
            purchase_invoice=processed_purchase_invoice,
            document_number="20260700012",
            application_date=date(2026, 7, 18),
            concepts_payment_pjd=IslrPjdChoices.HONORARIOS_PROFESIONALES,
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
        )
    
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.clean()
        assert "purchase_invoice" in exc_info.value.error_dict
        assert exc_info.value.error_dict["purchase_invoice"][0].code == "invalid_invoice_status"
        
    def test_retroactive_application_date_raises_validation_error_ID_EC_004(
        self,
        tenant_profile: FiscalProfile,
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Evita la declaración con fechas fiscales inferiores a la emisión de la factura."""
        # Arrange
        # Factura emitida el 2026-07-15
        certificate = IslrWithholdingCertificate(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700013",
            application_date=date(2026, 7, 14),  # Fecha retroactiva inválida
            concepts_payment_pjd=IslrPjdChoices.HONORARIOS_PROFESIONALES,
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
        )
    
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.clean()
        assert "application_date" in exc_info.value.error_dict
        assert "retroactive_application_date" in exc_info.value.error_dict["application_date"][0].code

    def test_invalid_correlative_structure_raises_validation_error_ID_EC_005(
        self,
        tenant_profile: FiscalProfile,
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Rechaza números de correlativo discrepantes al período de la fecha de aplicación."""
        # Arrange
        certificate = IslrWithholdingCertificate(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260600001",  # Prefijo 202606 no corresponde a Julio (202607)
            application_date=date(2026, 7, 18),
            concepts_payment_pjd=IslrPjdChoices.HONORARIOS_PROFESIONALES,
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
        )
    
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.clean()
        assert "document_number" in exc_info.value.error_dict
        assert "invalid_correlative_structure" in exc_info.value.error_dict["document_number"][0].code

    def test_mutation_on_processed_record_raises_validation_error_ID_EC_006(
        self, 
        tenant_profile: FiscalProfile, 
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Asegura la inmutabilidad de registros con estado PROCESSED bloqueando mutaciones."""
        # Arrange
        certificate = IslrWithholdingCertificate.objects.create(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700015",
            application_date=date(2026, 7, 18),
            concepts_payment_pjd=IslrPjdChoices.HONORARIOS_PROFESIONALES,
        )
        # Cambio forzado de estado simulando un cierre fiscal previo
        IslrWithholdingCertificate.objects.filter(pk=certificate.pk).update(
            status=IslrWithholdingCertificate.CertificateStatus.PROCESSED
        )
        certificate.refresh_from_db()

        # Act & Assert
        certificate.document_number = "20260799999"
        with pytest.raises(ValidationError) as exc_info:
            certificate.save()
        assert "immutable_record_processed" in exc_info.value.code

    def test_deletion_on_processed_record_raises_validation_error_ID_EC_007(
        self, 
        tenant_profile: FiscalProfile, 
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Impide la eliminación física de registros cerrados por auditoría fiscal."""
        # Arrange
        certificate = IslrWithholdingCertificate.objects.create(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700016",
            application_date=date(2026, 7, 18),
            concepts_payment_pjd=IslrPjdChoices.HONORARIOS_PROFESIONALES,
        )
        IslrWithholdingCertificate.objects.filter(pk=certificate.pk).update(
            status=IslrWithholdingCertificate.CertificateStatus.PROCESSED
        )
        certificate.refresh_from_db()

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.delete()
        assert "protected_record_processed" in exc_info.value.code

    def test_duplicate_document_number_per_tenant_raises_integrity_error_ID_EC_008(
        self, 
        tenant_profile: FiscalProfile, 
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Controla duplicados bloqueando registros concurrentes con igual correlativo."""
        # Arrange
        IslrWithholdingCertificate.objects.create(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700017",
            application_date=date(2026, 7, 18),
            concepts_payment_pjd=IslrPjdChoices.HONORARIOS_PROFESIONALES,
        )

        # Creación de una segunda factura paralela para adjuntar el duplicado
        another_invoice = PurchaseLedgerInvoice.objects.create(
            fiscal_profile=tenant_profile,
            supplier=preliminary_purchase_invoice.supplier,
            number="FACT-2026-002",
            invoice_control="CTRL-00200",
            date=date(2026, 7, 15),
            application_month_year="07-2026",
            taxable_base=Decimal("100.00"),
            total_purchase=Decimal("116.00")
        )

        duplicate_certificate = IslrWithholdingCertificate(
            fiscal_profile=tenant_profile,
            purchase_invoice=another_invoice,
            document_number="20260700017",  # Mismo correlativo e inquilino
            application_date=date(2026, 7, 18),
            concepts_payment_pjd=IslrPjdChoices.HONORARIOS_PROFESIONALES,
        )

        # Act & Assert
        with pytest.raises(IntegrityError):
            duplicate_certificate.save()

    def test_pnr_under_fixed_factor_returns_zero_values_ID_EC_009(
        self, 
        tenant_profile: FiscalProfile, 
        preliminary_purchase_invoice: PurchaseLedgerInvoice
    ) -> None:
        """Valida retención en cero cuando el subtotal es inferior al factor legal (PNR)."""
        # Arrange
        # Subtotal bajo (1000.00 / 150 UT = 6.66 UT), muy inferior a fixed_factor = 83.3334 UT
        preliminary_purchase_invoice.taxable_base = Decimal("1000.00")
        preliminary_purchase_invoice.subtotal = Decimal("1000.00")
        preliminary_purchase_invoice.save()

        # Act
        certificate = IslrWithholdingCertificate.objects.create(
            fiscal_profile=tenant_profile,
            purchase_invoice=preliminary_purchase_invoice,
            document_number="20260700018",
            application_date=date(2026, 7, 18),
            concepts_payment_pnr=IslrPnrChoices.HONORARIOS_PROFESIONALES,
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY
        )

        # Assert
        assert certificate.subtracting == Decimal("0.00")
        assert certificate.islr_withheld_amount == Decimal("0.00")