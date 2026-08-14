"""Suite de Pruebas Unitarias para el modelo IslrWithholdingCertificate.

Verifica reglas de negocio integrales, validaciones de temporalidad,
cálculos automáticos, bloqueos de inmutabilidad y exclusividad de conceptos.
"""
from typing import Any
from datetime import date
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError

from data_access.models.islr_withholding import IslrWithholdingCertificate
from data_access.models.concep_payment_islr import (
    IslrPnnrChoices,
    IslrPnrChoices,
    IslrPjdChoices,
    IslrPjndChoices,
)

pytestmark = pytest.mark.django_db

class TestIslrWithholdingCertificate:
    """Suite de pruebas para validaciones y restricciones del certificado de retención ISLR."""

    # =========================================================================
    # HAPPY PATHS (Flujos Felices)
    # =========================================================================

    def test_clean_hp_001_validacion_exitosa(self, preliminary_invoice, base_fiscal_profile):
        """[ID_HP_001] Verifica validación exitosa de reglas de negocio integrales en clean()."""
        
        # Arrange
        certificate = IslrWithholdingCertificate(
            purchase_invoice=preliminary_invoice,  # Instancia de modelo y no cadena
            document_number="2026080001",
            application_date=date(2026, 8, 10),
            fiscal_profile=base_fiscal_profile,    # Instancia de modelo y no cadena
            concepts_payment_pnnr=1,
            islr_withheld_amount=Decimal("0.00"),
        )

        # Act & Assert
        try:
            certificate.clean()
        except ValidationError:
            pytest.fail("clean() arrojó ValidationError inesperadamente en flujo feliz [ID_HP_001].")

    def test_save_hp_002_guardado_exitoso_preliminary(self, preliminary_invoice, base_fiscal_profile):
        """[ID_HP_002] Confirma que la creación de registro invoque cálculo automático y persista."""
        
        # Arrange
        certificate = IslrWithholdingCertificate(
            purchase_invoice=preliminary_invoice,
            document_number="2026080002",
            application_date=date(2026, 8, 10),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pjd=1,
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY,
        )

        # Act
        certificate.save()

        # Assert
        assert certificate.pk is not None, "El comprobante no fue guardado en BD."
        assert certificate.islr_withheld_amount > Decimal("0.00"), "El monto de retención no fue calculado."

    def test_save_hp_003_actualizacion_comprobante_preliminary(self, preliminary_invoice, base_fiscal_profile):
        """[ID_HP_003] Valida que un comprobante PRELIMINARY permita ser modificado y guardado."""
        
        # Arrange
        certificate = IslrWithholdingCertificate.objects.create(
            purchase_invoice=preliminary_invoice,
            document_number="2026080003",
            application_date=date(2026, 8, 11),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pjd=1,
            islr_withheld_amount=Decimal("10.00"),
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY,
        )
        
        # Act
        certificate.document_number = "2026080099"
        certificate.save()

        # Assert
        certificate.refresh_from_db()
        assert certificate.document_number == "2026080099", "La actualización no se reflejó correctamente."

    def test_delete_hp_004_eliminacion_exitosa_preliminary(self, preliminary_invoice, base_fiscal_profile):
        """[ID_HP_004] Verifica que un registro en estado PRELIMINARY pueda ser eliminado."""
        
        # Arrange
        certificate = IslrWithholdingCertificate.objects.create(
            purchase_invoice=preliminary_invoice,
            document_number="2026080004",
            application_date=date(2026, 8, 12),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pjd=1,
            islr_withheld_amount=Decimal("10.00"),
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY,
        )
        cert_id = certificate.pk

        # Act
        certificate.delete()

        # Assert
        assert not IslrWithholdingCertificate.objects.filter(pk=cert_id).exists(), "El certificado no fue eliminado."

    def test_clean_hp_005_validacion_temporalidad_fechas_identicas(self, preliminary_invoice, base_fiscal_profile):
        """[ID_HP_005] Comprueba que la validación sea exitosa cuando application_date == invoice_date."""
        
        # Arrange
        preliminary_invoice.date = date(2026, 8, 12)
        preliminary_invoice.save()
        
        certificate = IslrWithholdingCertificate(
            purchase_invoice=preliminary_invoice,
            document_number="2026081001",
            application_date=date(2026, 8, 12),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pjd=1,
            islr_withheld_amount=Decimal("0.00"),
        )

        # Act & Assert
        try:
            certificate.clean()
        except ValidationError:
            pytest.fail("clean() falló con fechas idénticas [ID_HP_005].")

    # =========================================================================
    # EDGE CASES (Casos Borde y Manejo de Errores)
    # =========================================================================

    def test_clean_ec_001_factura_asociada_no_preliminar(self, processed_invoice, base_fiscal_profile):
        """[ID_EC_001] Evalúa restricción que prohíbe comprobantes en facturas no preliminares."""
        
        # Arrange
        certificate = IslrWithholdingCertificate(
            purchase_invoice=processed_invoice,
            document_number="2026080005",
            application_date=date(2026, 8, 21),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pnnr=1,
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.clean()
            
        assert 'purchase_invoice' in exc_info.value.error_dict
        assert exc_info.value.error_dict['purchase_invoice'][0].code == 'invalid_invoice_status'

    def test_clean_ec_002_correlativo_documento_discordante(self, preliminary_invoice, base_fiscal_profile):
        """[ID_EC_002] Fuerza fallo cuando el documento no corresponde a YYYYMM de application_date."""
        
        # Arrange
        certificate = IslrWithholdingCertificate(
            purchase_invoice=preliminary_invoice,
            document_number="2026070001",  # Discordante con application_date (08)
            application_date=date(2026, 8, 15),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pjd=1,
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.clean()

        assert 'document_number' in exc_info.value.error_dict
        assert exc_info.value.error_dict['document_number'][0].code == 'invalid_correlative_structure'

    def test_clean_ec_003_aplicacion_fiscal_retroactiva(self, preliminary_invoice, base_fiscal_profile):
        """[ID_EC_003] Evalúa regla de temporalidad fiscal impidiendo fecha aplicación < fecha factura."""
        
        # Arrange
        preliminary_invoice.date = date(2026, 8, 10)
        preliminary_invoice.save()

        certificate = IslrWithholdingCertificate(
            purchase_invoice=preliminary_invoice,
            document_number="2026080001",
            application_date=date(2026, 8, 1), # Fecha inferior a la factura
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pjd=1,
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.clean()

        assert 'application_date' in exc_info.value.error_dict
        assert exc_info.value.error_dict['application_date'][0].code == 'retroactive_application_date'

    def test_clean_ec_004_ausencia_total_conceptos_retencion(self, preliminary_invoice, base_fiscal_profile):
        """[ID_EC_004] Comprueba comportamiento si no se selecciona ningún concepto de retención."""
        
        # Arrange
        certificate = IslrWithholdingCertificate(
            purchase_invoice=preliminary_invoice,
            document_number="2026080001",
            application_date=date(2026, 8, 10),
            fiscal_profile=base_fiscal_profile,
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.clean()

        # Las validaciones que arrojan cadenas crudas se agrupan en error_list o listan su primer error
        assert getattr(exc_info.value, 'code', exc_info.value.error_list[0].code) == 'missing_islr_concept'

    def test_clean_ec_005_violacion_exclusividad_mutua(self, preliminary_invoice, base_fiscal_profile):
        """[ID_EC_005] Evalúa control que prohíbe asignar múltiples conceptos en el mismo comprobante."""
        
        # Arrange
        certificate = IslrWithholdingCertificate(
            purchase_invoice=preliminary_invoice,
            document_number="2026080001",
            application_date=date(2026, 8, 10),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pnr=1,
            concepts_payment_pjd=1, # Selección múltiple
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.clean()

        assert exc_info.value.error_list[0].code == 'multiple_islr_concepts'

    def test_clean_ec_006_acumulacion_multiples_errores(self, processed_invoice, base_fiscal_profile):
        """[ID_EC_006] Verifica que el método recopile todas las violaciones en un solo diccionario."""
        
        # Arrange
        processed_invoice.date = date(2026, 8, 20)
        processed_invoice.save()

        certificate = IslrWithholdingCertificate(
            purchase_invoice=processed_invoice,
            document_number="ABC-12345",       # Formato inválido
            application_date=date(2026, 8, 1), # Retroactivo
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pjd=1,
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.clean()

        error_dict = exc_info.value.error_dict
        assert 'purchase_invoice' in error_dict
        assert 'document_number' in error_dict
        assert 'application_date' in error_dict

        assert error_dict['purchase_invoice'][0].code == 'invalid_invoice_status'
        assert error_dict['document_number'][0].code == 'invalid_correlative_structure'
        assert error_dict['application_date'][0].code == 'retroactive_application_date'

    def test_save_ec_007_intento_actualizacion_processed(self, preliminary_invoice, base_fiscal_profile):
        """[ID_EC_007] Garantiza el bloqueo de inmutabilidad sobre comprobante PROCESSED."""
        
        # Arrange
        certificate = IslrWithholdingCertificate.objects.create(
            purchase_invoice=preliminary_invoice,
            document_number="2026080007",
            application_date=date(2026, 8, 10),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pjd=1,
            islr_withheld_amount=Decimal("10.00"),
            status=IslrWithholdingCertificate.CertificateStatus.PROCESSED,
        )

        # Act & Assert
        certificate.document_number = "2026080099"
        with pytest.raises(ValidationError) as exc_info:
            certificate.save()
            
        assert exc_info.value.error_list[0].code == 'immutable_record_processed'

    def test_delete_ec_008_intento_eliminacion_processed(self, preliminary_invoice, base_fiscal_profile):
        """[ID_EC_008] Valida la protección fiscal que impide destrucción de comprobantes procesados."""
        
        # Arrange
        certificate = IslrWithholdingCertificate.objects.create(
            purchase_invoice=preliminary_invoice,
            document_number="2026080008",
            application_date=date(2026, 8, 10),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pjd=1,
            islr_withheld_amount=Decimal("10.00"),
            status=IslrWithholdingCertificate.CertificateStatus.PROCESSED,
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.delete()
            
        assert exc_info.value.error_list[0].code == 'protected_record_processed'

    def test_save_ec_010_concepto_con_ut_invalida(self, preliminary_invoice, base_fiscal_profile):
        """[ID_EC_010] Comprueba fallo controlado si el perfil fiscal posee UT inválida o nula."""
        
        # Arrange
        base_fiscal_profile.ut = Decimal("0.00")
        base_fiscal_profile.save()

        certificate = IslrWithholdingCertificate(
            purchase_invoice=preliminary_invoice,
            document_number="2026080010",
            application_date=date(2026, 8, 10),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pjnd=1,
            status=IslrWithholdingCertificate.CertificateStatus.PRELIMINARY,
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            certificate.save()

        assert exc_info.value.error_list[0].code == 'invalid_ut_value'

    def test_clean_ec_011_atributos_opcionales_nulos(self, preliminary_invoice, base_fiscal_profile):
        """[ID_EC_011] Verifica la resiliencia al recibir campos vacíos que participan en evaluaciones."""
        
        # Arrange
        certificate = IslrWithholdingCertificate(
            purchase_invoice=preliminary_invoice,
            document_number=None,
            application_date=None,
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pnnr=1,
        )

        # Act & Assert
        try:
            certificate.clean()
        except ValidationError as exc_info:
            # Tolerancia estructural: el método no debe colapsar por TypeError/AttributeError
            error_dict = getattr(exc_info, 'error_dict', {})
            assert 'document_number' not in error_dict
            assert 'application_date' not in error_dict


@pytest.mark.django_db
class TestConceptsPayment:
    """Suite de pruebas automatizadas para el concepto de pago PNR."""

    @pytest.mark.parametrize(
        "code, concept_val, subtotal, expected_base, expected_islr, expected_sust",
        [
            ("002", 1, "1000.00", "1000.00", "0.00", "0.00"),
            ("012", 3, "4000.00", "4000.00", "12.50", "107.50"),
            ("041", 7, "1000.00", "1000.00", "340.00", "0.00"),
        ],
    )
    def test_concepts_payment_pnr_happy_path(
        self,
        preliminary_invoice: Any,
        base_fiscal_profile: Any,
        code: str,
        concept_val: int,
        subtotal: str,
        expected_base: str,
        expected_islr: str,
        expected_sust: str,
    ) -> None:
        """Verifica que el modelo calcule el monto retenido y el sustraendo para PNR."""
        # Arrange
        preliminary_invoice.subtotal = Decimal(subtotal)
        preliminary_invoice.save()

        certificate = IslrWithholdingCertificate(
            purchase_invoice=preliminary_invoice,
            document_number="2026080003",
            application_date=date(2026, 8, 15),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pnr=concept_val,
        )

        # Act
        certificate.save()

        # Assert
        assert certificate.islr_withheld_amount == Decimal(expected_islr)
        assert certificate.subtracting == Decimal(expected_sust)


    """Suite de pruebas automatizadas para el concepto de pago PNNR."""

    @pytest.mark.parametrize(
        "code, concept_val, subtotal, expected_base, expected_islr",
        [
            ("003", 1, "1000.00", "900.00", "306.00"),
            ("015", 4, "1000.00", "1000.00", "340.00"),
            ("022", 6, "1000.00", "950.00", "323.00"),
            ("032", 8, "1000.00", "250.00", "85.00"),
            ("036", 10, "1000.00", "300.00", "102.00"),
            ("038", 11, "1000.00", "500.00", "170.00"),
        ],
    )
    def test_concepts_payment_pnnr_happy_path(
        self,
        preliminary_invoice: Any,
        base_fiscal_profile: Any,
        code: str,
        concept_val: int,
        subtotal: str,
        expected_base: str,
        expected_islr: str,
    ) -> None:
        """Verifica que el modelo calcule correctamente la retención según el código SENIAT."""
        # Arrange
        preliminary_invoice.subtotal = Decimal(subtotal)
        preliminary_invoice.save()

        certificate = IslrWithholdingCertificate(
            purchase_invoice=preliminary_invoice,
            document_number="2026080001",
            application_date=date(2026, 8, 15),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pnnr=concept_val,
        )

        # Act
        certificate.save()

        # Assert
        assert certificate.islr_withheld_amount == Decimal(expected_islr)


    """Suite de pruebas automatizadas para el concepto de pago PJD."""

    @pytest.mark.parametrize(
        "code, concept_val, subtotal, expected_base, expected_islr",
        [
            ("004", 1, "1000.00", "1000.00", "50.00"),
            ("072", 13, "1000.00", "1000.00", "30.00"),
        ],
    )
    def test_concepts_payment_pjd_happy_path(
        self,
        preliminary_invoice: Any,
        base_fiscal_profile: Any,
        code: str,
        concept_val: int,
        subtotal: str,
        expected_base: str,
        expected_islr: str,
    ) -> None:
        """Verifica el enrutamiento y cálculo matemático simple sobre PJD."""
        # Arrange
        preliminary_invoice.subtotal = Decimal(subtotal)
        preliminary_invoice.save()

        certificate = IslrWithholdingCertificate(
            purchase_invoice=preliminary_invoice,
            document_number="2026080007",
            application_date=date(2026, 8, 15),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pjd=concept_val,
        )

        # Act
        certificate.save()

        # Assert
        assert certificate.islr_withheld_amount == Decimal(expected_islr)


    """Suite de pruebas automatizadas para el concepto de pago PJND."""

    @pytest.mark.parametrize(
        "code, concept_val, subtotal, expected_base, expected_islr, expected_sust",
        [
            ("005", 1, "1000.00", "900.00", "135.00", "0.00"),
            ("017", 2, "1000.00", "1000.00", "50.00", "0.00"),
            ("023", 4, "128000.00", "121600.00", "20732.00", "6020.00"),
            ("024", 5, "1000.00", "1000.00", "49.50", "0.00"),
            ("028", 6, "200000.00", "190000.00", "43100.00", "21500.00"),
        ],
    )
    def test_concepts_payment_pjnd_happy_path(
        self,
        preliminary_invoice: Any,
        base_fiscal_profile: Any,
        code: str,
        concept_val: int,
        subtotal: str,
        expected_base: str,
        expected_islr: str,
        expected_sust: str,
    ) -> None:
        """Verifica retención progresiva (Tarifa N° 2) y tasas fijas para PJND."""
        # Arrange
        preliminary_invoice.subtotal = Decimal(subtotal)
        preliminary_invoice.save()

        # Ajuste de UT a 43.00 en base de datos para encajar el cálculo matemático con el test plan
        #base_fiscal_profile.ut = Decimal("43.00")
        #base_fiscal_profile.save()

        certificate = IslrWithholdingCertificate(
            purchase_invoice=preliminary_invoice,
            document_number="2026080005",
            application_date=date(2026, 8, 15),
            fiscal_profile=base_fiscal_profile,
            concepts_payment_pjnd=concept_val,
        )

        # Act
        certificate.save()

        # Assert
        assert certificate.islr_withheld_amount == Decimal(expected_islr)
        
        # Nota contractual de Testing: Si la lógica actual del modelo omite volcar
        # `sustraendo_bs` en la propiedad `self.subtracting`, este test fallará sirviendo 
        # como red de seguridad para forzar la corrección en la capa lógica.
        assert getattr(certificate, "subtracting", Decimal("0.00")) == Decimal(expected_sust)
    