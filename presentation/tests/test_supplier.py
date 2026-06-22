"""Suite de pruebas de integración para las vistas CRUD de proveedores locales.

Verifica el aislamiento multi-inquilino (tenant) interactuando directamente
con la base de datos real, evaluando el comportamiento de las vistas sin
el uso de mocks para garantizar un entorno de prueba 100% integrado.
"""

import pytest
from django.urls import reverse
from django.test import Client

from data_access.models.base import FiscalProfile
from data_access.models.supplier import LocalSupplier


@pytest.mark.django_db
@pytest.mark.integration
class TestLocalSupplierIntegration:
    """Pruebas de integración estructuradas para presentation/views/supplier.py.
    
    Nota: La vista actualmente extrae el inquilino activo mediante
    `FiscalProfile.objects.first()`. Para simular el entorno de forma nativa,
    garantizamos que `tenant_a_profile` sea creado primero en la base de datos
    pasándolo como primer argumento en la inyección de dependencias de pytest.
    """

    def test_hp_001_list_isolated_by_fiscal_profile(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
        tenant_b_profile: FiscalProfile,
        tenant_a_suppliers: list[LocalSupplier],
        tenant_b_supplier: LocalSupplier,
    ) -> None:
        """[ID_HP_001] Verifica el listado aislado excluyendo registros ajenos."""
        # Arrange
        url = reverse("supplier-list")

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 200
        assert "suppliers" in response.context
        context_suppliers = list(response.context["suppliers"])
        assert len(context_suppliers) == 3
        assert tenant_b_supplier not in context_suppliers

    def test_hp_002_detail_view_authorized(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
        tenant_a_suppliers: list[LocalSupplier],
    ) -> None:
        """[ID_HP_002] Visualización del detalle íntegro de un proveedor autorizado."""
        # Arrange
        target_supplier = tenant_a_suppliers[0]
        url = reverse("supplier-detail", kwargs={"code": target_supplier.code})

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 200
        assert response.context["supplier"] == target_supplier
        assert target_supplier.rif in response.content.decode()

    def test_hp_003_create_new_supplier(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
    ) -> None:
        """[ID_HP_003] Inserción exitosa de un proveedor local inédito."""
        # Arrange
        url = reverse("supplier-create")
        payload = {
            "name": "Nuevo Proveedor Inédito C.A.",
            "rif": "J-99999999-9",
            "supplier_type": LocalSupplier.SupplierType.WITH_RIF,
            "vat_withholding_percentage": "75.00",
        }

        # Act
        response = client.post(url, data=payload)

        # Assert
        new_supplier = LocalSupplier.objects.get(rif="J-99999999-9")
        assert response.status_code == 302
        assert response.url == reverse("supplier-detail", kwargs={"code": new_supplier.code})
        assert new_supplier.fiscal_profile == tenant_a_profile

    def test_hp_004_create_idempotent_existing_rif(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
        tenant_a_suppliers: list[LocalSupplier],
    ) -> None:
        """[ID_HP_004] Idempotencia al crear un proveedor con RIF existente."""
        # Arrange
        existing_supplier = tenant_a_suppliers[0]
        url = reverse("supplier-create")
        payload = {
            "name": "Nombre Alternativo C.A.",
            "rif": existing_supplier.rif,
            "supplier_type": LocalSupplier.SupplierType.WITH_RIF,
            "vat_withholding_percentage": "0.00",
        }

        # Act
        response = client.post(url, data=payload)

        # Assert
        assert response.status_code == 302
        assert response.url == reverse("supplier-detail", kwargs={"code": existing_supplier.code})
        # Verifica que no se generó un duplicado del RIF en el mismo perfil
        assert LocalSupplier.objects.filter(
            fiscal_profile=tenant_a_profile, rif=existing_supplier.rif
        ).count() == 1

    def test_hp_005_update_authorized_supplier(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
        tenant_a_suppliers: list[LocalSupplier],
    ) -> None:
        """[ID_HP_005] Actualización exitosa de los datos de un proveedor autorizado."""
        # Arrange
        target_supplier = tenant_a_suppliers[1]
        url = reverse("supplier-update", kwargs={"code": target_supplier.code})
        payload = {
            "name": "Proveedor A2 Actualizado C.A.",
            "rif": target_supplier.rif,
            "supplier_type": target_supplier.supplier_type,
            "vat_withholding_percentage": "100.00",
        }

        # Act
        response = client.post(url, data=payload)

        # Assert
        assert response.status_code == 302
        target_supplier.refresh_from_db()
        assert target_supplier.name == "Proveedor A2 Actualizado C.A."
        assert str(target_supplier.vat_withholding_percentage) == "100.00"

    def test_hp_006_delete_authorized_supplier(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
        tenant_a_suppliers: list[LocalSupplier],
    ) -> None:
        """[ID_HP_006] Eliminación física exitosa de un proveedor local."""
        # Arrange
        target_supplier = tenant_a_suppliers[2]
        url = reverse("supplier-delete", kwargs={"code": target_supplier.code})

        # Act
        response = client.post(url)

        # Assert
        assert response.status_code == 302
        assert response.url == reverse("supplier-list")
        assert not LocalSupplier.objects.filter(pk=target_supplier.pk).exists()

    def test_ec_001_detail_cross_tenant_returns_404(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
        tenant_b_profile: FiscalProfile,
        tenant_b_supplier: LocalSupplier,
    ) -> None:
        """[ID_EC_001] Prevención de acceso no autorizado a detalles de otro inquilino."""
        # Arrange
        # Al ejecutar bajo tenant_a_profile, intentamos acceder a un proveedor del tenant B
        url = reverse("supplier-detail", kwargs={"code": tenant_b_supplier.code})

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 404

    def test_ec_002_update_cross_tenant_returns_404(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
        tenant_b_profile: FiscalProfile,
        tenant_b_supplier: LocalSupplier,
    ) -> None:
        """[ID_EC_002] Prevención de modificación cruzada de datos."""
        # Arrange
        url = reverse("supplier-update", kwargs={"code": tenant_b_supplier.code})
        payload = {
            "name": "Intento de Hacking",
            "rif": tenant_b_supplier.rif,
            "supplier_type": LocalSupplier.SupplierType.WITH_RIF,
        }

        # Act
        response = client.post(url, data=payload)

        # Assert
        assert response.status_code == 404
        tenant_b_supplier.refresh_from_db()
        assert tenant_b_supplier.name != "Intento de Hacking"

    def test_ec_003_delete_cross_tenant_returns_404(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
        tenant_b_profile: FiscalProfile,
        tenant_b_supplier: LocalSupplier,
    ) -> None:
        """[ID_EC_003] Prevención de eliminación de registros de otro inquilino."""
        # Arrange
        url = reverse("supplier-delete", kwargs={"code": tenant_b_supplier.code})

        # Act
        response = client.post(url)

        # Assert
        assert response.status_code == 404
        assert LocalSupplier.objects.filter(pk=tenant_b_supplier.pk).exists()

    def test_ec_004_create_invalid_rif_returns_200_with_errors(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
    ) -> None:
        """[ID_EC_004] Intercepción de formulario con formato de RIF inválido."""
        # Arrange
        url = reverse("supplier-create")
        payload = {
            "name": "Proveedor RIF Inválido",
            "rif": "123456-A",
            "supplier_type": LocalSupplier.SupplierType.WITH_RIF,
        }

        # Act
        response = client.post(url, data=payload)

        # Assert
        assert response.status_code == 200
        assert "rif" in response.context["form"].errors

    def test_ec_005_create_missing_fields_returns_200_with_errors(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
    ) -> None:
        """[ID_EC_005] Invalidación de formulario por omisión de campos requeridos."""
        # Arrange
        url = reverse("supplier-create")
        payload = {
            "name": "",
            "rif": "",
            "supplier_type": LocalSupplier.SupplierType.WITH_RIF,
        }

        # Act
        response = client.post(url, data=payload)

        # Assert
        assert response.status_code == 200
        assert "name" in response.context["form"].errors
        assert "rif" in response.context["form"].errors

    def test_ec_006_detail_non_existent_code_returns_404(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
    ) -> None:
        """[ID_EC_006] Respuesta 404 controlada ante un identificador inexistente."""
        # Arrange
        url = reverse("supplier-detail", kwargs={"code": "PROV-99999"})

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 404

    def test_ec_007_null_fiscal_profile_context(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
        tenant_b_profile: FiscalProfile,
    ) -> None:
        """[ID_EC_007] Mitigación de fuga de datos cuando el perfil fiscal es nulo."""
        # Arrange
        # Destruimos todos los perfiles fiscales para forzar que `.first()` retorne None
        FiscalProfile.objects.all().delete()
        url = reverse("supplier-list")

        # Act
        response = client.get(url)

        # Assert
        # Django procesa `filter(fiscal_profile=None)` devolviendo un QuerySet vacío
        # garantizando que no haya fuga general de datos sin filtros.
        assert response.status_code == 200
        assert len(response.context["suppliers"]) == 0

    def test_ec_008_update_invalid_vat_percentage(
        self,
        client: Client,
        tenant_a_profile: FiscalProfile,
        tenant_a_suppliers: list[LocalSupplier],
    ) -> None:
        """[ID_EC_008] Bloqueo de inyección de porcentajes impositivos fuera de límite."""
        # Arrange
        target_supplier = tenant_a_suppliers[0]
        url = reverse("supplier-update", kwargs={"code": target_supplier.code})
        payload = {
            "name": target_supplier.name,
            "rif": target_supplier.rif,
            "supplier_type": target_supplier.supplier_type,
            "vat_withholding_percentage": "150.00",
        }

        # Act
        response = client.post(url, data=payload)

        # Assert
        assert response.status_code == 200
        assert "vat_withholding_percentage" in response.context["form"].errors
        target_supplier.refresh_from_db()
        assert str(target_supplier.vat_withholding_percentage) != "150.00"