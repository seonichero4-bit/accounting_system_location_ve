"""Suite de pruebas de integración para el Formulario y Vistas de SalesRecord.

Este módulo implementa el plan de pruebas especificado para validar la
inyección de contexto de inquilinos (tenants), restricciones de acceso,
y el manejo de errores de base de datos desde la capa de vistas.
"""

from typing import Any, Dict

import pytest
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse

# Se asume la ruta de importación de los modelos y componentes
from data_access.models.customer import Customer
from data_access.models.sales_record import SalesRecord
from data_access.models.base import FiscalProfile


# Constantes de rutas simuladas (se ajustan según el URLConf real del proyecto)
CREATE_URL = "/sales-records/create/"
UPDATE_URL_TEMPLATE = "/sales-records/update/{pk}/"


@pytest.mark.django_db
def test_ID_HP_001_inyeccion_contexto_inquilino_creacion(
    authenticated_client: Client,
    valid_sales_record_payload: Dict[str, Any],
    fiscal_profile: FiscalProfile
) -> None:
    """Valida la creación exitosa inyectando el perfil fiscal del inquilino."""
    # Arrange
    url = CREATE_URL
    initial_count = SalesRecord.objects.count()

    # Act
    response = authenticated_client.post(url, data=valid_sales_record_payload)

    # Assert
    assert response.status_code in [200, 302], "La vista debe procesar la solicitud exitosamente."
    assert SalesRecord.objects.count() == initial_count + 1
    new_record = SalesRecord.objects.latest('id')
    assert new_record.fiscal_profile == fiscal_profile
    assert new_record.document_number == valid_sales_record_payload["document_number"]


@pytest.mark.django_db
def test_ID_HP_002_filtrado_queryset_inquilino_formulario(
    authenticated_client: Client,
    other_tenant_customer: Customer
) -> None:
    """Verifica que los querysets del formulario estén aislados por inquilino."""
    # Arrange
    url = CREATE_URL

    # Act
    response = authenticated_client.get(url)

    # Assert
    assert response.status_code == 200
    form = response.context["form"]
    client_queryset = form.fields["client"].queryset
    assert other_tenant_customer not in client_queryset, (
        "El cliente de otro inquilino no debe ser visible en el formulario."
    )


@pytest.mark.django_db
def test_ID_HP_003_flujo_completo_edicion_registro_preliminar(
    authenticated_client: Client,
    persisted_sales_record: SalesRecord,
    valid_sales_record_payload: Dict[str, Any]
) -> None:
    """Comprueba la actualización exitosa de un registro preliminar."""
    # Arrange
    url = UPDATE_URL_TEMPLATE.format(pk=persisted_sales_record.pk)
    valid_sales_record_payload["document_number"] = "9999"

    # Act
    response = authenticated_client.post(url, data=valid_sales_record_payload)

    # Assert
    assert response.status_code in [200, 302]
    persisted_sales_record.refresh_from_db()
    assert persisted_sales_record.document_number == "9999"


@pytest.mark.django_db
def test_ID_EC_001_intento_seleccion_cliente_o_factura_otro_inquilino(
    authenticated_client: Client,
    valid_sales_record_payload: Dict[str, Any],
    other_tenant_customer: Customer
) -> None:
    """Evalúa que no se puedan asociar entidades de otro inquilino."""
    # Arrange
    url = CREATE_URL
    valid_sales_record_payload["client"] = other_tenant_customer.id

    # Act
    response = authenticated_client.post(url, data=valid_sales_record_payload)

    # Assert
    assert response.status_code == 200
    form = response.context["form"]
    assert "client" in form.errors
    assert "Escoja una opción válida" in str(form.errors["client"])


@pytest.mark.django_db
def test_ID_EC_002_aislamiento_consulta_por_inquilino_actualizacion(
    authenticated_client: Client,
    other_tenant_sales_record: SalesRecord
) -> None:
    """Valida restricción de acceso a registros de otros inquilinos (HTTP 404)."""
    # Arrange
    url = UPDATE_URL_TEMPLATE.format(pk=other_tenant_sales_record.pk)

    # Act
    response = authenticated_client.get(url)

    # Assert
    assert response.status_code == 404, "Debe retornar 404 por RequestScopedQuerySetMixin."


@pytest.mark.django_db
def test_ID_EC_003_alteracion_payload_post_campos_deshabilitados(
    authenticated_client: Client,
    valid_sales_record_payload: Dict[str, Any],
    other_tenant_profile: FiscalProfile,
    fiscal_profile: FiscalProfile
) -> None:
    """Probar que el formulario ignora inyecciones maliciosas de tenant IDs."""
    # Arrange
    url = CREATE_URL
    # Intento de asignación a un tenant distinto
    valid_sales_record_payload["fiscal_profile"] = other_tenant_profile.id

    # Act
    response = authenticated_client.post(url, data=valid_sales_record_payload)

    # Assert
    assert response.status_code in [200, 302]
    new_record = SalesRecord.objects.latest('id')
    assert new_record.fiscal_profile == fiscal_profile
    assert new_record.fiscal_profile != other_tenant_profile


@pytest.mark.django_db
def test_ID_EC_004_intercepcion_error_unicidad_documento(
    authenticated_client: Client,
    persisted_sales_record: SalesRecord,
    valid_sales_record_payload: Dict[str, Any]
) -> None:
    """Valida la captura en la vista del IntegrityError de unicidad mapeado al formulario."""
    # Arrange
    url = CREATE_URL
    # Duplicamos los valores exactos para detonar unique_issued_document
    valid_sales_record_payload["control_number"] = persisted_sales_record.control_number
    valid_sales_record_payload["document_type"] = persisted_sales_record.document_type
    
    # Comprobación de borde directo (simulando IntegrityError a bajo nivel si se invoca manual)
    with pytest.raises(IntegrityError):
        duplicate_record = SalesRecord(
            fiscal_profile=persisted_sales_record.fiscal_profile,
            client=persisted_sales_record.client,
            control_number=persisted_sales_record.control_number,
            document_type=persisted_sales_record.document_type,
            document_date=persisted_sales_record.document_date,
            # Se omiten campos obligatorios irrelevantes para provocar la restricción de BD
        )
        duplicate_record.save()

    # Act
    response = authenticated_client.post(url, data=valid_sales_record_payload)

    # Assert
    assert response.status_code == 200
    form = response.context["form"]
    assert "control_number" in form.errors
    expected_msg = (
        "Ya existe un documento registrado con este N° de Control y "
        "Tipo de Documento para el perfil fiscal actual."
    )
    assert expected_msg in str(form.errors["control_number"])


@pytest.mark.django_db
def test_ID_EC_005_captura_excepcion_inmutabilidad_guardado(
    authenticated_client: Client,
    processed_sales_record: SalesRecord,
    valid_sales_record_payload: Dict[str, Any]
) -> None:
    """Evalúa captura del error por modificación de registro inmutable en estatus procesado."""
    # Arrange
    url = UPDATE_URL_TEMPLATE.format(pk=processed_sales_record.pk)

    # Act
    response = authenticated_client.post(url, data=valid_sales_record_payload)

    # Assert
    assert response.status_code == 200
    form = response.context["form"]
    assert form.non_field_errors()
    expected_msg = (
        "No se puede modificar un registro del Libro de Ventas que ya se "
        "encuentra en estatus 'Procesado' o 'Anulado Procesado'."
    )
    assert expected_msg in str(form.non_field_errors())