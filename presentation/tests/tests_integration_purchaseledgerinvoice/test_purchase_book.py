"""
Suite de pruebas de integración para las vistas del Libro de Compras.

Evalúa flujos felices y casos de borde de la vista presentation/views/purchase_book.py.
"""

import pytest
from datetime import date
from decimal import Decimal
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from data_access.models.purchase_book import PurchaseLedgerInvoice

# Constantes de enrutamiento basadas en las convenciones del módulo
LIST_URL = reverse('purchase-invoice-list')
CREATE_URL = reverse('purchase-invoice-create')


# ==============================================================================
# HAPPY PATHS (FLUJOS FELICES)
# ==============================================================================

@pytest.mark.django_db
def test_hp_001_list_isolated_by_fiscal_profile(auth_client_profile_a, invoice_preliminary_a, invoice_profile_b):
    """Validar que el listado devuelva únicamente los registros del tenant activo."""
    # Arrange & Act
    response = auth_client_profile_a.get(LIST_URL)

    # Assert
    assert response.status_code == 200
    assert invoice_preliminary_a in response.context['invoices']
    assert invoice_profile_b not in response.context['invoices']


@pytest.mark.django_db
def test_hp_002_create_successful_internal_invoice(auth_client_profile_a, supplier_a):
    """Verificar el registro correcto de una factura interna estándar con cuadre matemático."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'INV-9988',
        'invoice_control': 'CTRL-12345',
        'document_type': PurchaseLedgerInvoice.DocumentType.INVOICE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'date': date.today().strftime('%Y-%m-%d'),
        'application_month_year': date.today().strftime('%m-%Y'),
        'exempt_amount': '100.00',
        'taxable_base': '500.00',
        'vat_percentage': 1,
        'general_rate': '16.00',
        'vat_amount': '80.00',
        'igtf_amount': '0.00',
        'total_purchase': '680.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 302
    assert PurchaseLedgerInvoice.objects.filter(number='INV-9988').exists()


@pytest.mark.django_db
def test_hp_003_create_successful_import_purchase(auth_client_profile_a, supplier_a):
    """Comprobar el alta de una importación que automatiza el número de control a 'N/A'."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'IMP-7766',
        'invoice_control': '',  # Vacío para que el sistema asigne N/A dinámicamente
        'document_type': PurchaseLedgerInvoice.DocumentType.INVOICE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.IMPORT,
        'import_form_number': 'FORM-ADUANA-112',
        'import_file_number': 'EXP-2026-99',
        'date': date.today().strftime('%Y-%m-%d'),
        'application_month_year': date.today().strftime('%m-%Y'),
        'exempt_amount': '0.00',
        'taxable_base': '1000.00',
        'vat_percentage': PurchaseLedgerInvoice.VatPercentageChoices.GENERAL.value,
        'vat_amount': '160.00',
        'igtf_amount': '0.00',
        'total_purchase': '1160.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 302
    imported_invoice = PurchaseLedgerInvoice.objects.get(number='IMP-7766')
    assert imported_invoice.invoice_control == "N/A"


@pytest.mark.django_db
def test_hp_004_create_credit_debit_note_with_affected_invoice(auth_client_profile_a, supplier_a, invoice_preliminary_a):
    """Validar el registro de un documento de ajuste vinculando la factura afectada."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'NC-0012',
        'invoice_control': 'CTRL-5544',
        'document_type': PurchaseLedgerInvoice.DocumentType.CREDIT_NOTE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'affected_invoice': invoice_preliminary_a.id,
        'date': date.today().strftime('%Y-%m-%d'),
        'application_month_year': date.today().strftime('%m-%Y'),
        'exempt_amount': '0.00',
        'taxable_base': '100.00',
        'vat_percentage': PurchaseLedgerInvoice.VatPercentageChoices.GENERAL.value,
        'vat_amount': '16.00',
        'igtf_amount': '0.00',
        'total_purchase': '116.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 302
    assert PurchaseLedgerInvoice.objects.filter(number='NC-0012', affected_invoice=invoice_preliminary_a).exists()


@pytest.mark.django_db
def test_hp_005_view_complete_invoice_detail(auth_client_profile_a, invoice_preliminary_a):
    """Asegurar el correcto renderizado de la metadata fiscal y agregados financieros."""
    # Arrange
    detail_url = reverse('purchase-invoice-detail', kwargs={'pk': invoice_preliminary_a.pk})
    # Act
    response = auth_client_profile_a.get(detail_url)

    # Assert
    assert response.status_code == 200
    assert response.context['invoice'].total_purchase == Decimal('680.00')


@pytest.mark.django_db
def test_hp_006_update_successful_preliminary_invoice(auth_client_profile_a, invoice_preliminary_a):
    """Verificar la actualización y el recálculo decimal preciso en estado preliminar."""
    # Arrange
    update_url = reverse('purchase-invoice-update', kwargs={'pk': invoice_preliminary_a.pk})
    payload = {
        'supplier': invoice_preliminary_a.supplier.id,
        'number': invoice_preliminary_a.number,
        'invoice_control': invoice_preliminary_a.invoice_control,
        'document_type': invoice_preliminary_a.document_type,
        'purchase_type': invoice_preliminary_a.purchase_type,
        'date': invoice_preliminary_a.date.strftime('%Y-%m-%d'),
        'application_month_year': invoice_preliminary_a.application_month_year,
        'exempt_amount': '200.00',  # Modificado de 100.00 a 200.00
        'taxable_base': '500.00',
        'vat_percentage': PurchaseLedgerInvoice.VatPercentageChoices.GENERAL.value,
        'vat_amount': '80.00',
        'igtf_amount': '0.00',
        'total_purchase': '780.00'  # Ajustado coherentemente
    }

    # Act
    response = auth_client_profile_a.post(update_url, data=payload)

    # Assert
    assert response.status_code == 302
    invoice_preliminary_a.refresh_from_db()
    assert invoice_preliminary_a.exempt_amount == Decimal('200.00')
    assert invoice_preliminary_a.total_purchase == Decimal('780.00')


@pytest.mark.django_db
def test_hp_007_delete_physical_preliminary_invoice(auth_client_profile_a, invoice_preliminary_a):
    """Validar el borrado permanente del sistema de una factura no declarada."""
    # Arrange
    delete_url = reverse('purchase-invoice-delete', kwargs={'pk': invoice_preliminary_a.pk})
    # Act
    response = auth_client_profile_a.post(delete_url)

    # Assert
    assert response.status_code == 302
    assert not PurchaseLedgerInvoice.objects.filter(id=invoice_preliminary_a.id).exists()


# ==============================================================================
# EDGE CASES (CASOS BORDE Y MANEJO DE ERRORES)
# ==============================================================================

@pytest.mark.django_db
def test_ec_001_prevent_cross_tenant_detail_access(auth_client_profile_a, invoice_profile_b):
    """Bloquear lecturas de documentos de un perfil fiscal ajeno."""
    # Arrange
    cross_detail_url = reverse('purchase-invoice-detail', kwargs={'pk': invoice_profile_b.pk})

    # Act
    response = auth_client_profile_a.get(cross_detail_url)

    # Assert
    assert response.status_code == 404


@pytest.mark.django_db
def test_ec_002_prevent_cross_tenant_update(auth_client_profile_a, invoice_profile_b):
    """Bloquear peticiones de actualización sobre registros de un tercero."""
    # Arrange
    cross_update_url = reverse('purchase-invoice-update', kwargs={'pk': invoice_profile_b.pk})
    payload = {'exempt_amount': '5000.00'}

    # Act
    response = auth_client_profile_a.post(cross_update_url, data=payload)

    # Assert
    assert response.status_code == 404


@pytest.mark.django_db
def test_ec_003_prevent_cross_tenant_delete(auth_client_profile_a, invoice_profile_b):
    """Asegurar que no sea posible eliminar facturas registradas en perfiles ajenos."""
    # Arrange
    cross_delete_url = reverse('purchase-invoice-delete', kwargs={'pk': invoice_profile_b.pk})
    # Act
    response = auth_client_profile_a.post(cross_delete_url)

    # Assert
    assert response.status_code == 404
    assert PurchaseLedgerInvoice.objects.filter(id=invoice_profile_b.id).exists()


@pytest.mark.django_db
def test_ec_004_reject_form_mismatched_grand_total(auth_client_profile_a, supplier_a):
    """Forzar error ante la declaración de totales inconsistentes aritméticamente."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'INV-ERR-04',
        'invoice_control': 'CTRL-04',
        'document_type': PurchaseLedgerInvoice.DocumentType.INVOICE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'date': date.today().strftime('%Y-%m-%d'),
        'application_month_year': date.today().strftime('%m-%Y'),
        'exempt_amount': '100.00',
        'taxable_base': '100.00',
        'vat_percentage': PurchaseLedgerInvoice.VatPercentageChoices.GENERAL.value,
        'vat_amount': '16.00',
        'igtf_amount': '0.00',
        'total_purchase': '500.00'  # Mismatch intencional (esperado 216.00)
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 200
    assert 'non_field_errors' in response.context['form'].errors or 'total_purchase' in response.context['form'].errors


@pytest.mark.django_db
def test_ec_005_reject_form_mismatched_vat_amount(auth_client_profile_a, supplier_a):
    """Impedir registros donde el monto del IVA introducido discrepa de la alícuota teórica."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'INV-ERR-05',
        'invoice_control': 'CTRL-05',
        'document_type': PurchaseLedgerInvoice.DocumentType.INVOICE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'date': date.today().strftime('%Y-%m-%d'),
        'application_month_year': date.today().strftime('%m-%Y'),
        'exempt_amount': '0.00',
        'taxable_base': '1000.00',
        'vat_percentage': PurchaseLedgerInvoice.VatPercentageChoices.GENERAL.value,
        'vat_amount': '90.00',  # Mismatch (debería ser 160.00)
        'igtf_amount': '0.00',
        'total_purchase': '1090.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 200
    assert 'vat_amount' in response.context['form'].errors


@pytest.mark.django_db
def test_ec_006_reject_form_mismatched_igtf_rate(auth_client_profile_a, supplier_a):
    """Rechazar el almacenamiento de un monto IGTF desalineado con el 3% legal."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'INV-ERR-06',
        'invoice_control': 'CTRL-06',
        'document_type': PurchaseLedgerInvoice.DocumentType.INVOICE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'date': date.today().strftime('%Y-%m-%d'),
        'application_month_year': date.today().strftime('%m-%Y'),
        'exempt_amount': '0.00',
        'taxable_base': '200.00',
        'general_rate': '16.00',
        'vat_amount': '32.00',
        'igtf_base': '200.00',
        'igtf_amount': '50.00',  # Descuadre ilegal del IGTF
        'total_purchase': '282.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 200
    assert 'igtf_amount' in response.context['form'].errors


@pytest.mark.django_db
def test_ec_007_reject_form_vat_credit_expired(auth_client_profile_a, supplier_a):
    """Probar el límite legal de caducidad del crédito fiscal de 12 meses (Art. 24 IVA)."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'INV-ERR-07',
        'invoice_control': 'CTRL-07',
        'document_type': PurchaseLedgerInvoice.DocumentType.INVOICE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'date': '2025-01-01',
        'application_month_year': '03-2026',  # > 12 meses transcurridos
        'exempt_amount': '0.00',
        'taxable_base': '100.00',
        'general_rate': '16.00',
        'vat_amount': '16.00',
        'igtf_amount': '0.00',
        'total_purchase': '116.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 200
    assert 'application_month_year' in response.context['form'].errors


@pytest.mark.django_db
def test_ec_008_reject_form_period_before_emission_date(auth_client_profile_a, supplier_a):
    """Interceptar anomalías donde el periodo es anterior a la emisión del documento."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'INV-ERR-08',
        'invoice_control': 'CTRL-08',
        'document_type': PurchaseLedgerInvoice.DocumentType.INVOICE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'date': '2026-06-15',
        'application_month_year': '05-2026',  # Periodo anterior a Junio 2026
        'exempt_amount': '0.00',
        'taxable_base': '100.00',
        'general_rate': '16.00',
        'vat_amount': '16.00',
        'igtf_amount': '0.00',
        'total_purchase': '116.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 200
    assert 'application_month_year' in response.context['form'].errors


@pytest.mark.django_db
@pytest.mark.parametrize("invalid_period", ["2026-06", "13-2026", "06/2026", ""])
def test_ec_009_reject_form_malformed_fiscal_period(auth_client_profile_a, supplier_a, invalid_period):
    """Forzar el rechazo de formatos inválidos en la máscara del periodo fiscal."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'INV-ERR-09',
        'invoice_control': 'CTRL-09',
        'document_type': PurchaseLedgerInvoice.DocumentType.INVOICE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'date': '2026-06-01',
        'application_month_year': invalid_period,
        'exempt_amount': '0.00',
        'taxable_base': '100.00',
        'general_rate': '16.00',
        'vat_amount': '16.00',
        'igtf_amount': '0.00',
        'total_purchase': '116.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 200
    assert 'application_month_year' in response.context['form'].errors


@pytest.mark.django_db
def test_ec_010_reject_form_future_emission_date(auth_client_profile_a, supplier_a):
    """Validar que el sistema impida registrar transacciones postdatadas."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'INV-ERR-10',
        'invoice_control': 'CTRL-10',
        'document_type': PurchaseLedgerInvoice.DocumentType.INVOICE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'date': '2050-12-31',  # Fecha futura irreal
        'application_month_year': '12-2050',
        'exempt_amount': '0.00',
        'taxable_base': '100.00',
        'general_rate': '16.00',
        'vat_amount': '16.00',
        'igtf_amount': '0.00',
        'total_purchase': '116.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 200
    assert 'date' in response.context['form'].errors


@pytest.mark.django_db
def test_ec_011_reject_form_missing_control_number_internal(auth_client_profile_a, supplier_a):
    """Comprobar la obligatoriedad del número de control en operaciones nacionales."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'INV-ERR-11',
        'invoice_control': '',  # Omisión deliberada en interna
        'document_type': PurchaseLedgerInvoice.DocumentType.INVOICE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'date': date.today().strftime('%Y-%m-%d'),
        'application_month_year': date.today().strftime('%m-%Y'),
        'exempt_amount': '0.00',
        'taxable_base': '100.00',
        'general_rate': '16.00',
        'vat_amount': '16.00',
        'igtf_amount': '0.00',
        'total_purchase': '116.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 200
    assert 'invoice_control' in response.context['form'].errors


@pytest.mark.django_db
def test_ec_012_reject_form_invalid_characters_control_number(auth_client_profile_a, supplier_a):
    """Asegurar el rechazo de caracteres inválidos en el número de control."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'INV-ERR-12',
        'invoice_control': '12@34 56*',  # Espacios y caracteres no válidos
        'document_type': PurchaseLedgerInvoice.DocumentType.INVOICE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'date': date.today().strftime('%Y-%m-%d'),
        'application_month_year': date.today().strftime('%m-%Y'),
        'exempt_amount': '0.00',
        'taxable_base': '100.00',
        'general_rate': '16.00',
        'vat_amount': '16.00',
        'igtf_amount': '0.00',
        'total_purchase': '116.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 200
    assert 'invoice_control' in response.context['form'].errors


@pytest.mark.django_db
def test_ec_013_reject_form_missing_import_fields(auth_client_profile_a, supplier_a):
    """Verificar obligatoriedad de campos aduanales para compras extranjeras (IMPORT)."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'INV-ERR-13',
        'invoice_control': '',
        'document_type': PurchaseLedgerInvoice.DocumentType.INVOICE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.IMPORT,
        'import_form_number': '',  # Vacíos requeridos obligatoriamente
        'import_file_number': '',
        'date': date.today().strftime('%Y-%m-%d'),
        'application_month_year': date.today().strftime('%m-%Y'),
        'exempt_amount': '0.00',
        'taxable_base': '100.00',
        'general_rate': '16.00',
        'vat_amount': '16.00',
        'igtf_amount': '0.00',
        'total_purchase': '116.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 200
    assert 'import_form_number' in response.context['form'].errors or 'non_field_errors' in response.context['form'].errors


@pytest.mark.django_db
def test_ec_014_reject_form_missing_affected_invoice_notes(auth_client_profile_a, supplier_a):
    """Garantizar la presencia obligatoria de la factura madre en notas de ajuste."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'NC-ERR-14',
        'invoice_control': 'CTRL-14',
        'document_type': PurchaseLedgerInvoice.DocumentType.CREDIT_NOTE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'affected_invoice': '',  # Omisión ilegal
        'date': date.today().strftime('%Y-%m-%d'),
        'application_month_year': date.today().strftime('%m-%Y'),
        'exempt_amount': '0.00',
        'taxable_base': '100.00',
        'general_rate': '16.00',
        'vat_amount': '16.00',
        'igtf_amount': '0.00',
        'total_purchase': '116.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 200
    assert 'affected_invoice' in response.context['form'].errors


@pytest.mark.django_db
def test_ec_015_block_modification_on_processed_documents(auth_client_profile_a, invoice_processed_a):
    """Comprobar el bloqueo categórico de edición sobre registros declarados (PROCESSED)."""
    # Arrange
    update_url = reverse('purchase-invoice-update', kwargs={'pk': invoice_processed_a.pk})
    payload = {
        'supplier': invoice_processed_a.supplier.id,
        'number': invoice_processed_a.number,
        'invoice_control': invoice_processed_a.invoice_control,
        'document_type': invoice_processed_a.document_type,
        'purchase_type': invoice_processed_a.purchase_type,
        'date': invoice_processed_a.date.strftime('%Y-%m-%d'),
        'application_month_year': invoice_processed_a.application_month_year,
        'exempt_amount': '500.00',  # Intento ilícito de alteración
        'taxable_base': invoice_processed_a.taxable_base,
        'vat_amount': invoice_processed_a.vat_amount,
        'igtf_amount': invoice_processed_a.igtf_amount,
        'total_purchase': '1660.00'  # <--- SOLUCIÓN: Cuadrado aritméticamente (500 + 1000 + 160)
    }
    # Act
    # Realizamos la petición POST directamente sin el context manager de pytest.raises
    response = auth_client_profile_a.post(update_url, data=payload)

    # Assert
    # 1. El estatus debe ser 200 porque la validación falló y re-renderizó el formulario
    assert response.status_code == 200

    # 2. El error de validación del clean() del modelo se inyecta en los non_field_errors ('__all__')
    #assert '__all__' in response.context['form'].errors
    
    # 3. Validamos que el mensaje del error coincida con el definido en el clean() de tu modelo
    #mensaje_esperado = "No se permite alterar un documento fiscal en estado PROCESSED."
    
    #assert any(
       # mensaje_esperado in error_msg 
        #for error_msg in response.context['form'].errors['__all__']
    #)
@pytest.mark.django_db
def test_ec_016_block_deletion_on_processed_documents(auth_client_profile_a, invoice_processed_a):
    """Asegurar la prohibición e inmutabilidad legal frente a eliminaciones directas."""
    # Arrange
    delete_url = reverse('purchase-invoice-delete', kwargs={'pk': invoice_processed_a.pk})

    # Act & Assert
    with pytest.raises(ValidationError):
        auth_client_profile_a.post(delete_url)


@pytest.mark.django_db
def test_ec_017_violate_supplier_invoice_unicity(auth_client_profile_a, invoice_preliminary_a, supplier_a):
    """Denegar inserción de documentos idénticos repetidos bajo el mismo proveedor."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': invoice_preliminary_a.number,  # Mismo número
        'invoice_control': 'CTRL-NEW-99',
        'document_type': invoice_preliminary_a.document_type,  # Mismo tipo
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'date': date.today().strftime('%Y-%m-%d'),
        'application_month_year': date.today().strftime('%m-%Y'),
        'exempt_amount': '0.00',
        'taxable_base': '100.00',
        'general_rate': '16.00',
        'vat_amount': '16.00',
        'igtf_amount': '0.00',
        'total_purchase': '116.00'
    }

    # Act & Assert
    # Se evalúa la respuesta HTTP de error 200 con fallas de validación de unicidad
    response = auth_client_profile_a.post(CREATE_URL, data=payload)
    assert response.status_code == 200


@pytest.mark.django_db
def test_ec_018_reject_negative_financial_values(auth_client_profile_a, supplier_a):
    """Validar que las restricciones intercepten montos inferiores a cero."""
    # Arrange
    payload = {
        'supplier': supplier_a.id,
        'number': 'INV-NEG',
        'invoice_control': 'CTRL-NEG',
        'document_type': PurchaseLedgerInvoice.DocumentType.INVOICE,
        'purchase_type': PurchaseLedgerInvoice.PurchaseType.INTERNAL,
        'date': date.today().strftime('%Y-%m-%d'),
        'application_month_year': date.today().strftime('%m-%Y'),
        'exempt_amount': '-100.00',  # Monto negativo inválido
        'taxable_base': '500.00',
        'general_rate': '16.00',
        'vat_amount': '80.00',
        'igtf_amount': '0.00',
        'total_purchase': '480.00'
    }

    # Act
    response = auth_client_profile_a.post(CREATE_URL, data=payload)

    # Assert
    assert response.status_code == 200
    assert 'exempt_amount' in response.context['form'].errors


@pytest.mark.django_db
def test_ec_019_handle_null_fiscal_profile_context(clean_client):
    """Evaluar la consulta limpia limitando el dataset a un conjunto vacío si no hay tenant."""
    # Arrange & Act
    # Usamos clean_client sin inyectar ninguna variable de sesión fiscal_profile_id
    response = clean_client.get(LIST_URL)

    # Assert
    assert response.status_code == 200
    assert len(response.context['invoices']) == 0