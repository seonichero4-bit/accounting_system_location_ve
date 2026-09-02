"""Suite de pruebas de integración para las vistas y formulario del modelo Customer.

Cubre los casos de éxito y de borde definidos en el plan de pruebas para los
componentes CustomerCreateView, CustomerUpdateView y CustomerForm.
"""

from typing import Any, Dict

import pytest
from django.test import Client
from django.urls import reverse

from data_access.models.base import FiscalProfile
from data_access.models.customer import Customer


@pytest.mark.django_db
def test_customer_create_valid_mandatory_data_ID_HP_001(
    authenticated_client: Client,
    valid_customer_post_data: Dict[str, Any],
    fiscal_profile: FiscalProfile
) -> None:
    """Valida la creación exitosa con datos obligatorios y perfil fiscal desenvuelto."""
    # Arrange: Preparación
    url = reverse("customer_create")
    payload = valid_customer_post_data.copy()
    payload.pop("custom_accounts_receivable", None)
    payload.pop("custom_income_account", None)

    # Act: Acción
    response = authenticated_client.post(url, data=payload)

    # Assert: Verificación
    assert response.status_code == 302
    assert Customer.objects.filter(rif=payload["rif"]).exists()
    customer = Customer.objects.get(rif=payload["rif"])
    assert customer.fiscal_profile == fiscal_profile


@pytest.mark.django_db
def test_customer_create_custom_accounts_same_tenant_ID_HP_002(
    authenticated_client: Client,
    valid_customer_post_data: Dict[str, Any],
    fiscal_profile: FiscalProfile
) -> None:
    """Verifica la asociación de cuentas contables del mismo inquilino."""
    # Arrange: Preparación
    url = reverse("customer_create")
    payload = valid_customer_post_data

    # Act: Acción
    response = authenticated_client.post(url, data=payload)

    # Assert: Verificación
    assert response.status_code == 302
    customer = Customer.objects.get(rif=payload["rif"])
    assert customer.custom_accounts_receivable_id == payload["custom_accounts_receivable"]
    assert customer.custom_income_account_id == payload["custom_income_account"]
    assert customer.fiscal_profile == fiscal_profile


@pytest.mark.django_db
def test_customer_update_allowed_fields_same_tenant_ID_HP_003(
    authenticated_client: Client,
    persisted_customer: Customer,
    fiscal_profile: FiscalProfile
) -> None:
    """Valida la actualización de atributos permitidos sin alterar el perfil fiscal."""
    # Arrange: Preparación
    url = reverse("customer_update", kwargs={"pk": persisted_customer.pk})
    payload = {
        "rif": persisted_customer.rif,
        "name": persisted_customer.name,
        "taxpayer_type": persisted_customer.taxpayer_type,
        "fiscal_address": "Av. Bolívar, Local 5",
        "phone_number": "02125559876",
    }

    # Act: Acción
    response = authenticated_client.post(url, data=payload)

    # Assert: Verificación
    assert response.status_code == 302
    persisted_customer.refresh_from_db()
    assert persisted_customer.fiscal_address == "Av. Bolívar, Local 5"
    assert persisted_customer.phone_number == "02125559876"
    assert persisted_customer.fiscal_profile == fiscal_profile


@pytest.mark.django_db
def test_customer_create_accounts_other_tenant_ID_EC_001(
    authenticated_client: Client,
    valid_customer_post_data: Dict[str, Any],
    secondary_customer_accounts: Dict[str, Any]
) -> None:
    """Valida el rechazo al intentar asociar cuentas contables de otro inquilino."""
    # Arrange: Preparación
    url = reverse("customer_create")
    payload = valid_customer_post_data.copy()
    payload["custom_accounts_receivable"] = secondary_customer_accounts["custom_accounts_receivable"].pk
    payload["custom_income_account"] = secondary_customer_accounts["custom_income_account"].pk

    # Act: Acción
    response = authenticated_client.post(url, data=payload)

    # Assert: Verificación
    assert response.status_code == 200
    assert "custom_accounts_receivable" in response.context["form"].errors
    assert "custom_income_account" in response.context["form"].errors
    assert not Customer.objects.filter(rif=payload["rif"]).exists()


@pytest.mark.django_db
def test_customer_update_other_tenant_returns_404_ID_EC_002(
    authenticated_client: Client,
    secondary_customer: Customer
) -> None:
    """Verifica que el intento de actualización de un cliente ajeno devuelva 404."""
    # Arrange: Preparación
    url = reverse("customer_update", kwargs={"pk": secondary_customer.pk})
    payload = {
        "fiscal_address": "Intento de intrusión",
        "phone_number": "00000000000"
    }

    # Act: Acción
    response = authenticated_client.post(url, data=payload)

    # Assert: Verificación
    assert response.status_code == 404
    secondary_customer.refresh_from_db()
    assert secondary_customer.fiscal_address != "Intento de intrusión"


@pytest.mark.django_db
def test_customer_create_malicious_fiscal_profile_tampering_ID_EC_003(
    authenticated_client: Client,
    valid_customer_post_data: Dict[str, Any],
    secondary_fiscal_profile: FiscalProfile,
    fiscal_profile: FiscalProfile
) -> None:
    """Verifica la omisión de un fiscal_profile malicioso inyectado en el POST."""
    # Arrange: Preparación
    url = reverse("customer_create")
    payload = valid_customer_post_data.copy()
    payload["fiscal_profile"] = secondary_fiscal_profile.pk

    # Act: Acción
    response = authenticated_client.post(url, data=payload)

    # Assert: Verificación
    assert response.status_code == 302
    customer = Customer.objects.get(rif=payload["rif"])
    assert customer.fiscal_profile == fiscal_profile
    assert customer.fiscal_profile != secondary_fiscal_profile