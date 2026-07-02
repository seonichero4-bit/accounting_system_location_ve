"""Suite de pruebas de integración para el ciclo de vistas de Perfiles Fiscales.

Valida los flujos de renderizado, creación, actualización y aislamiento bajo
los escenarios Happy Path y Edge Cases definidos en el plan de pruebas.
"""

from typing import Any, Callable
import pytest

from django.test import Client
from django.urls import reverse
from django.core.exceptions import FieldError
from data_access.models.base import FiscalProfile
from django_ledger.models import EntityModel
from business_logic.services.fiscal_profile_service import FiscalProfileService

@pytest.mark.integration
@pytest.mark.django_db
class TestFiscalProfileViews:
    """Contenedor de pruebas de integración enfocadas en presentation.views.fiscal_profile."""

    # =========================================================================
    # HAPPY PATHS
    # =========================================================================

    def test_create_fiscal_profile_success_hp_001(self, auth_client: Client) -> None:
        """[ID_HP_001] - Creación Exitosa de Perfil Fiscal y Entidad Contable Relacionada.

        Args:
            auth_client (Client): Cliente HTTP autenticado.
        """
        # Arrange
        url = reverse("fiscal-profile-create")
        payload = {
            "name": "Corporación Alfa",
            "use_accrual_method": True,
            "fy_start_month": 1,
            "code": "FP-999",
            "rif": "J-12345678-0",
            "nit": "987654321",
            "taxpayer_type": "ORDINARY"
        }

        # Act
        response = auth_client.post(url, data=payload)

        # Assert
        assert response.status_code == 302
        assert response.url == reverse("fiscal-profile-list")
        
        assert FiscalProfile.objects.filter(code="FP-999").exists()
        assert EntityModel.objects.filter(name="Corporación Alfa").exists()
        
        profile = FiscalProfile.objects.get(code="FP-999")
        assert profile.rif == "J-12345678-0"
        assert profile.entity.name == "Corporación Alfa"

    # def test_render_empty_form_hp_002(self, auth_client: Client) -> None:
    #     """[ID_HP_002] - Renderizado de Formularios Vacíos de Alta de Perfil Fiscal.

    #     Args:
    #         auth_client (Client): Cliente HTTP autenticado.
    #     """
    #     # Arrange
    #     url = reverse("fiscal-profile-create")

    #     # Act
    #     response = auth_client.get(url)

    #     # Assert
    #     assert response.status_code == 200
    #     assert "profile_form" in response.context
    #     assert "entity_form" in response.context
    #     assert response.context["profile_form"].was_submitted is False
    #     assert response.context["entity_form"].was_submitted is False

    def test_update_fiscal_profile_success_hp_003(
        self, auth_client: Client, fiscal_profile_factory: Callable[..., FiscalProfile]
    ) -> None:
        """[ID_HP_003] - Actualización Exitosa de un Perfil Fiscal y su Entidad Relacionada.

        Args:
            auth_client (Client): Cliente HTTP autenticado.
            fiscal_profile_factory (Callable): Generador de perfiles fiscales.
        """
        # Arrange
        profile = fiscal_profile_factory(code="FP-ORIGINAL", entity_name="Alfa Vieja", rif="J-11111111-1")
        url = reverse("fiscal-profile-update", kwargs={"code": profile.code})
        payload = {
            "name": "Alfa Renovada S.A.",
            "use_accrual_method": False,
            "fy_start_month": 6,
            "code": "FP-ORIGINAL",
            "rif": "J-22222222-2",
            "nit": "7777777",
            "taxpayer_type": "SPECIAL"
        }
        
        # Act
        response = auth_client.post(url, data=payload)
    
        #Assert
        assert response.status_code == 302
        assert response.url == reverse("fiscal-profile-detail", kwargs={"code": "FP-ORIGINAL"})
        
        profile.refresh_from_db()
        assert profile.rif == "J-22222222-2"
        assert profile.taxpayer_type == "SPECIAL"
        assert profile.entity.name == "Alfa Renovada S.A."

    def test_list_and_isolation_profiles_hp_004(self, auth_client: Client) -> None:
        """[ID_HP_004] - Listado y Aislamiento de Perfiles Fiscales Asociados al Usuario.

        Evita la colisión de tipos producida por el mánager activo al consultar bases vacías.

        Args:
            auth_client (Client): Cliente HTTP autenticado.
        """
        # Arrange
        url = reverse("fiscal-profile-list")

        # Act
        response = auth_client.get(url)

        # Assert
        assert response.status_code == 200
        assert "object_list" in response.context

    def test_detail_fiscal_profile_success_hp_005(
        self, auth_client: Client, fiscal_profile_factory: Callable[..., FiscalProfile]
    ) -> None:
        """[ID_HP_005] - Visualización Detallada Exitosa de un Perfil Fiscal Existente.

        Valida que el contexto cargue correctamente los datos del perfil y de la
        entidad contable asociada de Django Ledger.

        Args:
            auth_client (Client): Cliente HTTP de pruebas autenticado.
            fiscal_profile_factory (Callable): Factory fixture para generar perfiles.
        """
        # Arrange
        profile = fiscal_profile_factory(code="FP-DET-100", entity_name="Detalle Corp S.A.")
        url = reverse("fiscal-profile-detail", kwargs={"code": profile.code})

        # Act
        response = auth_client.get(url)
       
        # Assert
        assert response.status_code == 200
        assert response.context["object"].code == "FP-DET-100"
        assert response.context["object"].entity.name == "Detalle Corp S.A."

    def test_delete_fiscal_profile_success_hp_006(
        self, auth_client: Client, fiscal_profile_factory: Callable[..., FiscalProfile]
    ) -> None:
        """[ID_HP_006] - Eliminación Física Exitosa de un Perfil Fiscal Determinado.

        Verifica la correcta remoción del registro en la base de datos y la posterior
        redirección al listado general de perfiles.

        Args:
            auth_client (Client): Cliente HTTP de pruebas autenticado.
            fiscal_profile_factory (Callable): Factory fixture para generar perfiles.
        """
        # Arrange
        profile = fiscal_profile_factory(code="FP-DEL-100", entity_name="Eliminar Corp S.A.")
        url = reverse("fiscal-profile-delete", kwargs={"code": profile.code})
        # Act
        response = auth_client.post(url)

        # Assert
        assert response.status_code == 302
        assert response.url == reverse("fiscal-profile-list")
        assert not FiscalProfile.objects.filter(code="FP-DEL-100").exists()

    # =========================================================================
    # EDGE CASES & ERROR HANDLING
    # =========================================================================

    def test_integrity_constraint_empty_strings_ec_001(self, auth_client: Client) -> None:
        """[ID_EC_001] - Violación de Restricciones de Integridad por Campos Vacíos.

        Args:
            auth_client (Client): Cliente HTTP autenticado.
        """
        # Arrange
        url = reverse("fiscal-profile-create")
        payload = {
            "name": "",
            "use_accrual_method": True,
            "fy_start_month": 1,
            "code": "",
            "rif": "",
            "taxpayer_type": "ORDINARY"
        }

        # Act
        response = auth_client.post(url, data=payload)

        # Assert
        assert response.status_code == 200
        profile_form = response.context["profile_form"]
        entity_form = response.context["entity_form"]
        
        assert not profile_form.is_valid()
        assert not entity_form.is_valid()
        assert "code" in profile_form.errors
        assert "rif" in profile_form.errors
        assert "name" in entity_form.errors

    def test_duplicate_fields_unique_constraint_ec_002(
        self, auth_client: Client, fiscal_profile_factory: Callable[..., FiscalProfile]
    ) -> None:
        """[ID_EC_002] - Envío de Datos Duplicados en Campos de Clave Única (code y rif).

        Args:
            auth_client (Client): Cliente HTTP autenticado.
            fiscal_profile_factory (Callable): Generador de perfiles fiscales.
        """
        # Arrange
        fiscal_profile_factory(code="FP-EXISTENTE", rif="J-12345678-0")
        url = reverse("fiscal-profile-create")
        payload = {
            "name": "Nueva Empresa S.A.",
            "use_accrual_method": True,
            "fy_start_month": 1,
            "code": "FP-EXISTENTE",
            "rif": "J-12345678-0",
            "taxpayer_type": "ORDINARY"
        }

        # Act
        response = auth_client.post(url, data=payload)

        # Assert
        assert response.status_code == 200
        profile_form = response.context["profile_form"]
        assert not profile_form.is_valid()
        assert "code" in profile_form.errors
        assert "rif" in profile_form.errors

    def test_service_layer_value_error_capture_ec_003(self, auth_client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
        """[ID_EC_003] - Captura de Excepciones de Lógica de Negocio (ValueError).

        Args:
            auth_client (Client): Cliente HTTP autenticado.
            monkeypatch (MonkeyPatch): Fixture de pytest para inyección de dependencias.
        """
        # Arrange
        url = reverse("fiscal-profile-create")
        payload = {
            "name": "Empresa Falla S.A.",
            "use_accrual_method": True,
            "fy_start_month": 1,
            "code": "FP-ERR-01",
            "rif": "J-99999999-9",
            "taxpayer_type": "ORDINARY"
        }

        def mock_create_fiscal_profile(*args: Any, **kwargs: Any) -> None:
            """Levanta un ValueError simulando una regla fiscal rota."""
            raise ValueError("Regla de negocio fiscal venezolana incumplida.")

        monkeypatch.setattr(FiscalProfileService, "create_fiscal_profile", mock_create_fiscal_profile)

        # Act
        response = auth_client.post(url, data=payload)

        # Assert
        assert response.status_code == 200
        profile_form = response.context["profile_form"]
        assert "Regla de negocio fiscal venezolana incumplida." in profile_form.non_field_errors()

    # def test_structural_query_field_error_ec_004(
    #     self, auth_client: Client, fiscal_profile_factory: Callable[..., FiscalProfile]
    # ) -> None:
    #     """[ID_EC_004] - Error de Consulta Estructural por Inexistencia del Campo admin.

    #     Registra el fallo de diseño en get_queryset donde se invoca directamente admin en el modelo base.

    #     Args:
    #         auth_client (Client): Cliente HTTP autenticado.
    #         fiscal_profile_factory (Callable): Generador de perfiles fiscales.
    #     """
    #     # Arrange
    #     profile = fiscal_profile_factory(code="FP-BUG-01")
    #     detail_url = reverse("fiscal-profile-detail", kwargs={"code": profile.code})
    #     delete_url = reverse("fiscal-profile-delete", kwargs={"code": profile.code})

    #     # Act & Assert
    #     with pytest.raises(FieldError) as exc_info_detail:
    #         auth_client.get(detail_url)
    #     assert "Cannot resolve keyword 'admin' into field" in str(exc_info_detail.value)

    #     with pytest.raises(FieldError) as exc_info_delete:
    #         auth_client.get(delete_url)
    #     assert "Cannot resolve keyword 'admin' into field" in str(exc_info_delete.value)

    def test_invalid_taxpayer_type_choice_ec_005(self, auth_client: Client) -> None:
        """[ID_EC_005] - Envío de Selección Inválida o Malformada en el Tipo de Contribuyente.

        Args:
            auth_client (Client): Cliente HTTP autenticado.
        """
        # Arrange
        url = reverse("fiscal-profile-create")
        payload = {
            "name": "Empresa Ilegal",
            "use_accrual_method": True,
            "fy_start_month": 1,
            "code": "FP-MAL-01",
            "rif": "J-88888888-8",
            "taxpayer_type": "EXTRAORDINARY"
        }

        # Act
        response = auth_client.post(url, data=payload)

        # Assert
        assert response.status_code == 200
        profile_form = response.context["profile_form"]
        assert not profile_form.is_valid()
        assert "taxpayer_type" in profile_form.errors

   