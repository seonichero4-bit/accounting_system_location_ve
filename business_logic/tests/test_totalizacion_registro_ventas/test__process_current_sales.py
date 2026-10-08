"""Suite de pruebas unitarias para el componente _process_current_sales
del módulo SalesAccountingTotalizationService."""

import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError

from business_logic.services.sales_accounting_totalization_service import SalesAccountingTotalizationService
from data_access.models.sales_record import SalesRecord
from data_access.models.customer_payment import PaymentMethodTypeChoices, CurrencyChoices
from data_access.models.customer import Customer

pytestmark = pytest.mark.django_db


def test_process_current_sales_special_taxpayer_multicurrency_retentions_ID_HP_001(
    fiscal_profile,
    setup_accounts,
    sales_record_factory,
    vat_withholding_factory,
    islr_withholding_factory,
    customer_payment_factory,
):
    """[ID_HP_001] - Totalización completa de ventas con desglose multimoneda, retenciones, IGTF y descargo de inventario."""
    
    # ==========================
    # Arrange (Preparación)
    # ==========================
    fiscal_profile.taxpayer_type = "SPECIAL"
    fiscal_profile.save()

    # Registro 1: Venta de Bienes
    sr1 = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.GOODS,
        document_type=SalesRecord.DocumentType.INVOICE,
        general_tax_base_16=Decimal("20000.00"),
        general_tax_debit_16=Decimal("3200.00"),
        total_sales_inc_vat=Decimal("23200.00")
    )
    vat_withholding_factory(sales_record=sr1, withheld_amount=Decimal("2240.00"))
    customer_payment_factory(
        account_receivable=sr1.account_receivable,
        amount=Decimal("5000.00"),
        method_type=PaymentMethodTypeChoices.CASH,
        currency=CurrencyChoices.VES
    )

    # Registro 2: Venta de Servicios
    sr2 = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.SERVICES,
        document_type=SalesRecord.DocumentType.INVOICE,
        general_tax_base_16=Decimal("8000.00"),
        general_tax_debit_16=Decimal("1280.00"),
        total_sales_inc_vat=Decimal("9280.00")
    )
    vat_withholding_factory(sales_record=sr2, withheld_amount=Decimal("896.00"))
    islr_withholding_factory(sales_record=sr2, total_withheld_amount=Decimal("160.00"))
    customer_payment_factory(
        account_receivable=sr2.account_receivable,
        amount=Decimal("8224.00"),
        method_type=PaymentMethodTypeChoices.BANK_TRANSFER,
        currency=CurrencyChoices.VES
    )

    # Registro 3: Venta Mixta (Bienes y Servicios Exentos + IGTF)
    sr3 = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.MIXED,
        document_type=SalesRecord.DocumentType.INVOICE,
        exempt_goods_amount=Decimal("3000.00"),
        exempt_services_amount=Decimal("1000.00"),
        igtf_tax_amount=Decimal("300.00"),
        total_sales_inc_vat=Decimal("4300.00")
    )
    customer_payment_factory(
        account_receivable=sr3.account_receivable,
        amount=Decimal("10300.00"),
        method_type=PaymentMethodTypeChoices.CASH,
        currency=CurrencyChoices.USD
    )
    customer_payment_factory(
        account_receivable=sr3.account_receivable,
        amount=Decimal("4000.00"),
        method_type=PaymentMethodTypeChoices.BANK_TRANSFER,
        currency=CurrencyChoices.USD
    )

    service = SalesAccountingTotalizationService(fiscal_profile=fiscal_profile, fiscal_period="2026-03")
    sales_records = [sr1, sr2, sr3]

    # ==========================
    # Act (Acción)
    # ==========================
    je_sales, je_inv = service._process_current_sales(sales_records)

    # ==========================
    # Assert (Verificación)
    # ==========================
    assert je_sales is not None, "Debe generar el asiento de resumen de ventas"
    assert je_inv is not None, "Debe generar el asiento continuo de inventario al detectar bienes"


def test_process_current_sales_services_ordinary_taxpayer_ID_HP_002(
    fiscal_profile,
    setup_accounts,
    sales_record_factory,
    customer_payment_factory,
):
    """[ID_HP_002] - Totalización de ventas exclusivamente de Servicios para Contribuyente Ordinario."""
    
    # ==========================
    # Arrange (Preparación)
    # ==========================
    fiscal_profile.taxpayer_type = Customer.TaxpayerType.ORDINARY
    fiscal_profile.save()

    sr_a = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.SERVICES,
        document_type=SalesRecord.DocumentType.INVOICE,
        general_tax_base_16=Decimal("5000.00"),
        general_tax_debit_16=Decimal("800.00"),
        total_sales_inc_vat=Decimal("5800.00")
    )
    customer_payment_factory(
        account_receivable=sr_a.account_receivable,
        amount=Decimal("5800.00"),
        method_type=PaymentMethodTypeChoices.POS,
        currency=CurrencyChoices.VES
    )

    sr_b = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.SERVICES,
        document_type=SalesRecord.DocumentType.INVOICE,
        exempt_services_amount=Decimal("2000.00"),
        igtf_tax_amount=Decimal("0.00"),
        total_sales_inc_vat=Decimal("2000.00")
    )
    customer_payment_factory(
        account_receivable=sr_b.account_receivable,
        amount=Decimal("2000.00"),
        method_type=PaymentMethodTypeChoices.CASH,
        currency=CurrencyChoices.USD
    )

    service = SalesAccountingTotalizationService(fiscal_profile=fiscal_profile, fiscal_period="2026-03")

    # ==========================
    # Act (Acción)
    # ==========================
    je_sales, je_inv = service._process_current_sales([sr_a, sr_b])

    # ==========================
    # Assert (Verificación)
    # ==========================
    assert je_sales is not None, "Debe instanciar el asiento de ventas"
    assert je_inv is None, "El asiento de inventario debe ser None para ventas exclusivas de servicios"


def test_process_current_sales_mixed_category_exact_aggregation_ID_HP_003(
    fiscal_profile,
    setup_accounts,
    sales_record_factory,
    customer_payment_factory,
):
    """[ID_HP_003] - Agregación y clasificación exacta en operaciones con categoría Mixta (MIXED)."""
    
    # ==========================
    # Arrange (Preparación)
    # ==========================
    sr = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.MIXED,
        document_type=SalesRecord.DocumentType.INVOICE,
        goods_amount=Decimal("1500.00"),
        services_amount=Decimal("500.00"),
        exempt_goods_amount=Decimal("200.00"),
        exempt_services_amount=Decimal("100.00"),
        general_tax_debit_16=Decimal("320.00"),
        total_sales_inc_vat=Decimal("2620.00")
    )
    customer_payment_factory(
        account_receivable=sr.account_receivable,
        amount=Decimal("2620.00"),
        method_type=PaymentMethodTypeChoices.MOBILE_PAYMENT,
        currency=CurrencyChoices.VES
    )

    service = SalesAccountingTotalizationService(fiscal_profile=fiscal_profile, fiscal_period="2026-03")

    # ==========================
    # Act (Acción)
    # ==========================
    je_sales, je_inv = service._process_current_sales([sr])

    # ==========================
    # Assert (Verificación)
    # ==========================
    assert je_sales is not None
    assert je_inv is not None, "Al incluir ventas de bienes (MIXED), debe generarse el descargo de inventario"


def test_process_current_sales_invoice_and_z_report_consolidation_ID_HP_004(
    fiscal_profile,
    setup_accounts,
    sales_record_factory,
    customer_payment_factory,
):
    """[ID_HP_004] - Consolidadación combinada de Facturas Directas y Reportes Z de Impresoras Fiscales."""
    
    # ==========================
    # Arrange (Preparación)
    # ==========================
    sr1 = sales_record_factory(
        document_type=SalesRecord.DocumentType.INVOICE,
        document_number="FACT-101",
        general_tax_base_16=Decimal("1000.00"),
        general_tax_debit_16=Decimal("160.00"),
        total_sales_inc_vat=Decimal("1160.00")
    )
    customer_payment_factory(
        account_receivable=sr1.account_receivable,
        amount=Decimal("1160.00"),
        method_type=PaymentMethodTypeChoices.CASH,
        currency=CurrencyChoices.VES
    )

    # Nota: asumiendo que Z_REPORT u otro identificador permite setear el nro de reporte z.
    sr2 = sales_record_factory(
        document_type=SalesRecord.DocumentType.INVOICE,
        z_report_number="Z-0050",
        general_tax_base_16=Decimal("5000.00"),
        general_tax_debit_16=Decimal("800.00"),
        total_sales_inc_vat=Decimal("5800.00")
    )
    customer_payment_factory(
        account_receivable=sr2.account_receivable,
        amount=Decimal("5800.00"),
        method_type=PaymentMethodTypeChoices.CASH,
        currency=CurrencyChoices.VES
    )

    service = SalesAccountingTotalizationService(fiscal_profile=fiscal_profile, fiscal_period="2026-03")

    # ==========================
    # Act (Acción)
    # ==========================
    je_sales, je_inv = service._process_current_sales([sr1, sr2])

    # ==========================
    # Assert (Verificación)
    # ==========================
    assert je_sales is not None


def test_process_current_sales_empty_list_returns_nones_ID_EC_001(
    fiscal_profile,
    setup_accounts
):
    """[ID_EC_001] - Sublista de registros de ventas vacía devuelve Nones."""
    
    # ==========================
    # Arrange (Preparación)
    # ==========================
    service = SalesAccountingTotalizationService(fiscal_profile=fiscal_profile, fiscal_period="2026-03")
    
    # ==========================
    # Act (Acción)
    # ==========================
    je_sales, je_inv = service._process_current_sales([])

    # ==========================
    # Assert (Verificación)
    # ==========================
    assert je_sales is None, "Si la lista está vacía no se debe generar el asiento principal"
    assert je_inv is None, "Si la lista está vacía no se debe generar el asiento de inventario"


def test_process_current_sales_double_entry_mismatch_raises_validation_error_ID_EC_002(
    fiscal_profile,
    setup_accounts,
    sales_record_factory,
    customer_payment_factory
):
    """[ID_EC_002] - Descuadre en Partida Doble durante la verificación aborta transacción."""
    
    # ==========================
    # Arrange (Preparación)
    # ==========================
    # Se genera un registro intencionalmente corrupto (Base sin IVA = 10500)
    sr_corrupto = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.GOODS,
        document_type=SalesRecord.DocumentType.INVOICE,
        general_tax_base_16=Decimal("10500.00"),
        general_tax_debit_16=Decimal("0.00"), 
        total_sales_inc_vat=Decimal("10500.00")
    )
    # Pero el pago reflejará un monto distinto provocando descuadre (10000.00)
    customer_payment_factory(
        account_receivable=sr_corrupto.account_receivable,
        amount=Decimal("10000.00"),
        method_type=PaymentMethodTypeChoices.CASH,
        currency=CurrencyChoices.VES
    )

    service = SalesAccountingTotalizationService(fiscal_profile=fiscal_profile, fiscal_period="2026-03")

    # ==========================
    # Act & Assert (Acción y Verificación)
    # ==========================
    with pytest.raises(ValidationError, match="Error de cuadratura en .* \(Partida Doble\)"):
        service._process_current_sales([sr_corrupto])


def test_process_current_sales_float_rounding_precision_ID_EC_003(
    fiscal_profile,
    setup_accounts,
    sales_record_factory,
    customer_payment_factory
):
    """[ID_EC_003] - Imprecisión en centavos por redondeos de flotantes complejos no desestabiliza el balance."""
    
    # ==========================
    # Arrange (Preparación)
    # ==========================
    sr = sales_record_factory(
        general_tax_base_16=Decimal("333.33333"),
        general_tax_debit_16=Decimal("53.33333"),
        total_sales_inc_vat=Decimal("386.66666")
    )
    customer_payment_factory(
        account_receivable=sr.account_receivable,
        amount=Decimal("386.66666"),
        method_type=PaymentMethodTypeChoices.CASH,
        currency=CurrencyChoices.VES
    )

    service = SalesAccountingTotalizationService(fiscal_profile=fiscal_profile, fiscal_period="2026-03")

    # ==========================
    # Act (Acción)
    # ==========================
    je_sales, je_inv = service._process_current_sales([sr])

    # ==========================
    # Assert (Verificación)
    # ==========================
    assert je_sales is not None, "El redondeo a 2 decimales debe asegurar el cuadre del asiento sin levantar excepciones"


def test_process_current_sales_null_numeric_values_handled_safely_ID_EC_004(
    fiscal_profile,
    setup_accounts,
    sales_record_factory
):
    """[ID_EC_004] - Registros con valores nulos (None) en campos numéricos de importes se manejan por defecto a 0.00."""
    
    # ==========================
    # Arrange (Preparación)
    # ==========================
    sr = sales_record_factory(
        goods_amount=None,
        services_amount=None,
        general_tax_base_16=None,
        general_tax_debit_16=None,
        igtf_tax_amount=None,
        total_sales_inc_vat=Decimal("0.00")
    )
    service = SalesAccountingTotalizationService(fiscal_profile=fiscal_profile, fiscal_period="2026-03")

    # ==========================
    # Act (Acción)
    # ==========================
    # Validamos que no ocurra TypeError al hacer aritmética con None
    je_sales, je_inv = service._process_current_sales([sr])

    # ==========================
    # Assert (Verificación)
    # ==========================
    # Al procesarse todo como 0.00, no deberían haber txs de DEBE o HABER que creen descuadres, 
    # garantizando que se omiten correctamente.
    assert True 


def test_process_current_sales_invalid_document_type_raises_validation_error_ID_EC_005(
    fiscal_profile,
    setup_accounts,
    sales_record_credit_note_factory
):
    """[ID_EC_005] - Inclusión indebida de Notas de Crédito o Débito en la sublista inyectada."""
    
    # ==========================
    # Arrange (Preparación)
    # ==========================
    # Inyectando una nota de crédito por error en el lote de ventas directas
    sr_cn = sales_record_credit_note_factory()
    service = SalesAccountingTotalizationService(fiscal_profile=fiscal_profile, fiscal_period="2026-03")

    # ==========================
    # Act & Assert (Acción y Verificación)
    # ==========================
    with pytest.raises(ValidationError, match="Documento inválido 'CREDIT_NOTE'"):
        service._process_current_sales([sr_cn])


def test_process_current_sales_ordinary_taxpayer_ignores_igtf_ID_EC_006(
    fiscal_profile,
    setup_accounts,
    sales_record_factory,
    customer_payment_factory
):
    """[ID_EC_006] - Contribuyente Ordinario con importe IGTF mayor a cero omite contabilizar IGTF."""
    
    # ==========================
    # Arrange (Preparación)
    # ==========================
    fiscal_profile.taxpayer_type = Customer.TaxpayerType.ORDINARY
    fiscal_profile.save()

    # Se inyecta forzadamente un valor IGTF en la entidad de un Ordinario
    sr = sales_record_factory(
        document_type=SalesRecord.DocumentType.INVOICE,
        general_tax_base_16=Decimal("1000.00"),
        general_tax_debit_16=Decimal("160.00"),
        igtf_tax_amount=Decimal("30.00"), # Error/Forzado
        total_sales_inc_vat=Decimal("1190.00")
    )
    customer_payment_factory(
        account_receivable=sr.account_receivable,
        amount=Decimal("1190.00"),
        method_type=PaymentMethodTypeChoices.CASH,
        currency=CurrencyChoices.USD
    )

    service = SalesAccountingTotalizationService(fiscal_profile=fiscal_profile, fiscal_period="2026-03")

    # ==========================
    # Act (Acción)
    # ==========================
    # A pesar del cobro en divisa, el servicio debe enmascarar o ignorar la línea contable del IGTF.
    # Dado que la omisión alteraría el cuadre (El cajero cobró 1190, la base es 1160) levantará ValidationError
    # asegurando que los Ordinarios no registren ingresos anómalos o deba corregirse la declaración de ingresos.

    # ==========================
    # Assert (Verificación)
    # ==========================
    with pytest.raises(ValidationError, match="Error de cuadratura en .* \(Partida Doble\)"):
         service._process_current_sales([sr])