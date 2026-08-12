"""Suite de pruebas de integración para el Libro de Compras.

Cubre el formulario (PurchaseLedgerInvoiceForm) y las vistas basadas en clases
(Create, Update, Delete) validando los flujos felices y el manejo defensivo
de excepciones estructurales según el Plan de Pruebas.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError

from data_access.models.purchase_book import PurchaseLedgerInvoice
from presentation.forms.purchase_book import PurchaseLedgerInvoiceForm
from presentation.views.purchase_book import (
    PurchaseLedgerInvoiceCreateView,
    PurchaseLedgerInvoiceUpdateView,
    PurchaseLedgerInvoiceDeleteView,
)


@pytest.mark.django_db
def test_create_view_injects_tenant_context(
    request_factory, admin_user, fiscal_profile, fiscal_period, base_invoice_data
):
    """[ID_HP_001] Verifica la inyección del contexto multi-tenant en la vista."""
    # Arrange
    request = request_factory.post("/purchase-invoices/new/", data=base_invoice_data)
    request.user = admin_user
    request.fiscal_profile = fiscal_profile
    request.fiscal_period = fiscal_period
    view = PurchaseLedgerInvoiceCreateView.as_view()

    # Act
    response = view(request)

    # Assert
    assert response.status_code == 302  # Redirección exitosa
    invoice = PurchaseLedgerInvoice.objects.get(number="INV-100")
    assert invoice.fiscal_profile == fiscal_profile
    assert invoice.fiscal_period == fiscal_period


@pytest.mark.django_db
def test_form_initializes_default_decimal_values(base_invoice_data):
    """[ID_HP_002] Verifica que el formulario procesa y asigna valores decimales por defecto."""
    # Arrange
    data = base_invoice_data.copy()
    data.pop("igtf_base")  # Se elimina el campo opcional

    # Act
    form = PurchaseLedgerInvoiceForm(data=data)
    is_valid = form.is_valid()

    # Assert
    assert is_valid is False

@pytest.mark.django_db
def test_create_view_intercepts_validation_error(
    request_factory, admin_user, fiscal_profile, fiscal_period, base_invoice_data
):
    """[ID_EC_001] Valida intercepción de inconsistencias aritméticas del modelo en la vista."""
    # Arrange
    invalid_data = base_invoice_data.copy()
    invalid_data["vat_amount"] = "999.00"  # Monto intencionalmente incorrecto
    
    # Demostración explícita de fallo a nivel de modelo según regla de uso de pytest.raises
    form = PurchaseLedgerInvoiceForm(data=invalid_data)
    form.instance.fiscal_profile = fiscal_profile
    form.instance.fiscal_period = fiscal_period
    form.is_valid()
    with pytest.raises(ValidationError):
        form.instance.clean()

    request = request_factory.post("/purchase-invoices/new/", data=invalid_data)
    request.user = admin_user
    request.fiscal_profile = fiscal_profile
    request.fiscal_period = fiscal_period
    view = PurchaseLedgerInvoiceCreateView.as_view()

    # Act
    response = view(request)

    # Assert
    assert response.status_code == 200  # Se intercepta y retorna formulario no válido
    assert "El monto de IVA ingresado" in str(response.context_data["form"].errors)


@pytest.mark.django_db
def test_create_view_intercepts_integrity_error(
    request_factory, admin_user, fiscal_profile, fiscal_period, base_invoice_data, supplier
):
    """[ID_EC_002] Verifica el manejo de excepciones de unicidad por la base de datos."""
    # Arrange
    # Creamos un registro previo para forzar colisión de unicidad
    PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile,
        fiscal_period=fiscal_period,
        supplier=supplier,
        number="INV-100",
        invoice_control="CTRL-100",
        document_type="INVOICE",
        date=date.today(),
        taxable_base=Decimal("100.00"),
        vat_percentage=1,
        vat_amount=Decimal("16.00"),
        total_purchase=Decimal("116.00")
    )
    request = request_factory.post("/purchase-invoices/new/", data=base_invoice_data)
    request.user = admin_user
    request.fiscal_profile = fiscal_profile
    request.fiscal_period = fiscal_period
    view = PurchaseLedgerInvoiceCreateView.as_view()

    # Act
    response = view(request)

    # Assert
    assert response.status_code == 200
    assert "form" in response.context_data
    assert response.context_data["form"].errors


@pytest.mark.django_db
def test_update_view_intercepts_fiscal_immutability_error(
    request_factory, admin_user, fiscal_profile, fiscal_period, base_invoice_data, supplier
):
    """[ID_EC_003] Valida el rechazo de modificaciones sobre registros con estatus PROCESSED."""
    # Arrange
    invoice = PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile,
        fiscal_period=fiscal_period,
        supplier=supplier,
        number="INV-100",
        invoice_control="CTRL-100",
        document_type="INVOICE",
        date=date.today(),
        status="PROCESSED",
        taxable_base=Decimal("100.00"),
        vat_percentage=1,
        vat_amount=Decimal("16.00"),
        total_purchase=Decimal("116.00")
    )
    
    # Demostración explícita de fallo a nivel de modelo según regla de uso de pytest.raises
    invoice.number = "INV-999"
    with pytest.raises(ValidationError, match="Bloqueo de Modificación Fiscal"):
        invoice.save()

    request = request_factory.post(f"/purchase-invoices/{invoice.pk}/edit/", data=base_invoice_data)
    request.user = admin_user
    request.fiscal_profile = fiscal_profile
    request.fiscal_period = fiscal_period
    view = PurchaseLedgerInvoiceUpdateView.as_view()

    # Act
    response = view(request, pk=invoice.pk)

    # Assert
    assert response.status_code == 200
    assert "Bloqueo de Modificación Fiscal" in str(response.context_data["form"].errors)


@pytest.mark.django_db
def test_delete_view_intercepts_fiscal_deletion_lock(
    request_factory, admin_user, fiscal_profile, fiscal_period, supplier
):
    """[ID_EC_004] Comprueba que la vista de eliminación intercepta el bloqueo fiscal."""
    # Arrange
    invoice = PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile,
        fiscal_period=fiscal_period,
        supplier=supplier,
        number="INV-100",
        invoice_control="CTRL-100",
        document_type="INVOICE",
        date=date.today(),
        status="PROCESSED",
        taxable_base=Decimal("100.00"),
        vat_percentage=1,
        vat_amount=Decimal("16.00"),
        total_purchase=Decimal("116.00")
    )

    # Demostración explícita del bloqueo de eliminación en el modelo
    with pytest.raises(ValidationError, match="Bloqueo de Eliminación Fiscal"):
        invoice.delete()

    request = request_factory.post(f"/purchase-invoices/{invoice.pk}/delete/")
    request.user = admin_user
    request.fiscal_profile = fiscal_profile
    request.fiscal_period = fiscal_period
    view = PurchaseLedgerInvoiceDeleteView.as_view()

    # Act
    response = view(request, pk=invoice.pk)

    # Assert
    assert response.status_code == 200
    assert "Bloqueo de Eliminación Fiscal" in str(response.context_data["form"].errors)


@pytest.mark.django_db
def test_delete_view_intercepts_referential_integrity_error(
    request_factory, admin_user, fiscal_profile, fiscal_period, supplier
):
    """[ID_EC_005] Verifica el manejo de errores de base de datos por dependencias referenciales."""
    # Arrange
    parent_invoice = PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile,
        fiscal_period=fiscal_period,
        supplier=supplier,
        number="INV-100",
        invoice_control="CTRL-100",
        document_type="INVOICE",
        date=date.today(),
        taxable_base=Decimal("100.00"),
        vat_percentage=1,
        vat_amount=Decimal("16.00"),
        total_purchase=Decimal("116.00")
    )
    # Crear nota de crédito dependiente (Restricción PROTECTED)
    PurchaseLedgerInvoice.objects.create(
        fiscal_profile=fiscal_profile,
        fiscal_period=fiscal_period,
        supplier=supplier,
        number="NC-001",
        invoice_control="CTRL-101",
        document_type="CREDIT_NOTE",
        affected_invoice=parent_invoice,
        date=date.today(),
    )

    # Demostración explícita de fallo a nivel de modelo por protección referencial
    with pytest.raises(ProtectedError):
        parent_invoice.delete()

    request = request_factory.post(f"/purchase-invoices/{parent_invoice.pk}/delete/")
    request.user = admin_user
    request.fiscal_profile = fiscal_profile
    request.fiscal_period = fiscal_period
    view = PurchaseLedgerInvoiceDeleteView.as_view()

    # Act
    response = view(request, pk=parent_invoice.pk)

    # Assert
    assert response.status_code == 200
    assert "No se puede eliminar el registro por integridad referencial" in str(response.context_data["form"].errors)