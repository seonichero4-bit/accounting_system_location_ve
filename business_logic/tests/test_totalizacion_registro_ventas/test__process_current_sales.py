"""Suite de pruebas unitarias para el servicio de totalización de ventas.

Este módulo implementa las pruebas correspondientes a la consolidación contable
de ventas del período actual (`_process_current_sales`), validando la correcta
generación de partidas para el Libro Diario y el control de inventarios.
"""
from datetime import date
from decimal import Decimal
import pytest

from django_ledger.models import AccountModel

from data_access.models.base import FiscalProfile
from data_access.models.sales_record import SalesRecord
from data_access.models.customer_payment import CurrencyChoices, PaymentMethodTypeChoices
from business_logic.services.sales_accounting_totalization_service import SalesAccountingTotalizationService


def _get_account_amount(
    entries: list[tuple[AccountModel, Decimal, str]], account: AccountModel
) -> Decimal:
    """Helper para extraer el monto consolidado de una cuenta contable.
    
    Args:
        entries: Lista de tuplas de transacciones generadas.
        account: Cuenta contable de Django-Ledger a buscar.
        
    Returns:
        Monto consolidado asignado a la cuenta, o 0.00 si no existe.
    """
    for acc, amt, _ in entries:
        if acc == account:
            return amt
    return Decimal("0.00")


def _has_account(
    entries: list[tuple[AccountModel, Decimal, str]], account: AccountModel
) -> bool:
    """Helper para verificar si una cuenta contable fue incluida en el asiento.
    
    Args:
        entries: Lista de tuplas de transacciones generadas.
        account: Cuenta contable de Django-Ledger a buscar.
        
    Returns:
        True si la cuenta existe en la lista de entradas, False en caso contrario.
    """
    return any(acc == account for acc, amt, _ in entries)


# ==============================================================================
# HAPPY PATHS (Flujos Felices)
# ==============================================================================

@pytest.mark.django_db
def test_id_hp_001_consolidacion_estandar_ventas_bienes_y_servicios_moneda_nacional(
    fiscal_profile, setup_accounts, sales_record_factory, customer_payment_factory
):
    """[ID_HP_001] Validar consolidación contable estándar en moneda nacional.
    
    Combina ventas de bienes muebles y prestación de servicios, verificando cobros
    en caja y montos remanentes a crédito comercial.
    """
    # Arrange
    fiscal_profile.taxpayer_type = FiscalProfile.TaxpayerType.ORDINARY
    fiscal_profile.initial_fiscal_period.start_period = date(2026, 1, 1)
    fiscal_profile.save()

    # Factura 1: Bienes gravados pagados en efectivo
    sr1 = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.GOODS,
        general_tax_base_16=Decimal("1000.00"),
        general_tax_debit_16=Decimal("160.00"),
        total_sales_inc_vat=Decimal("1160.00"),
    )
    customer_payment_factory(
        account_receivable=sr1.account_receivable,
        amount=Decimal("1160.00"),
        currency=CurrencyChoices.VES,
        method_type=PaymentMethodTypeChoices.CASH,
    )

    # Factura 2: Servicios exentos a crédito
    sr2 = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.SERVICES,
        exempt_internal_sales=Decimal("500.00"),
        total_sales_inc_vat=Decimal("500.00"),
        general_tax_base_16=Decimal("0.00"),
        general_tax_debit_16=Decimal("0.00"),
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    sales_debit, sales_credit, inv_debit, inv_credit = service._process_current_sales([sr1, sr2])

    # Assert
    # DEBE
    assert _get_account_amount(sales_debit, setup_accounts["cash_national_account"]) == Decimal("1160.00")
    assert _get_account_amount(sales_debit, setup_accounts["ar_commercial_national_account"]) == Decimal("500.00")
    
    # HABER
    assert _get_account_amount(sales_credit, setup_accounts["taxable_goods_sales_account"]) == Decimal("1000.00")
    assert _get_account_amount(sales_credit, setup_accounts["exempt_services_sales_account"]) == Decimal("500.00")
    assert _get_account_amount(sales_credit, setup_accounts["vat_debit_account"]) == Decimal("160.00")
    
    # INVENTARIO
    assert _get_account_amount(inv_debit, setup_accounts["cogs_account"]) == Decimal("1.00")
    assert _get_account_amount(inv_credit, setup_accounts["inventory_account"]) == Decimal("1.00")


@pytest.mark.django_db
def test_id_hp_002_consolidacion_ventas_divisas_con_percepcion_igtf_spe(
    fiscal_profile, setup_accounts, sales_record_factory, customer_payment_factory
):
    """[ID_HP_002] Verificar adición de IGTF en divisas para Sujeto Pasivo Especial."""
    # Arrange
    fiscal_profile.taxpayer_type = FiscalProfile.TaxpayerType.SPECIAL
    fiscal_profile.initial_fiscal_period.start_period = date(2026, 1, 15)
    fiscal_profile.save()

    sr = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.GOODS,
        general_tax_base_16=Decimal("3600.00"),
        general_tax_debit_16=Decimal("576.00"),
        igtf_tax_base=Decimal("3600.00"),
        igtf_tax_amount=Decimal("108.00"),
        total_sales_inc_vat=Decimal("4176.00")
    )
    customer_payment_factory(
        account_receivable=sr.account_receivable,
        amount=Decimal("4176.00"),
        currency=CurrencyChoices.USD,
        method_type=PaymentMethodTypeChoices.CASH,
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    sales_debit, sales_credit, inv_debit, inv_credit = service._process_current_sales([sr])

    # Assert
    # DEBE: Cobrado (4176.00) + IGTF Percibido (108.00)
    assert _get_account_amount(sales_debit, setup_accounts["cash_foreign_account"]) == Decimal("4284.00")
    
    # HABER
    assert _get_account_amount(sales_credit, setup_accounts["taxable_goods_sales_account"]) == Decimal("3600.00")
    assert _get_account_amount(sales_credit, setup_accounts["vat_debit_account"]) == Decimal("576.00")
    assert _get_account_amount(sales_credit, setup_accounts["igtf_perceived_payable_account"]) == Decimal("108.00")


@pytest.mark.django_db
def test_id_hp_003_exclusion_percepcion_igtf_ordinario_cobro_divisas(
    fiscal_profile, setup_accounts, sales_record_factory, customer_payment_factory
):
    """[ID_HP_003] Confirmar que cobros en divisas NO generan IGTF en Ordinarios."""
    # Arrange
    fiscal_profile.taxpayer_type = FiscalProfile.TaxpayerType.ORDINARY
    fiscal_profile.initial_fiscal_period.start_period = date(2026, 1, 1)
    fiscal_profile.save()

    sr = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.GOODS,
        general_tax_base_16=Decimal("3600.00"),
        general_tax_debit_16=Decimal("576.00"),
        igtf_tax_amount=Decimal("0.00"),
        total_sales_inc_vat=Decimal("4176.00")
    )
    customer_payment_factory(
        account_receivable=sr.account_receivable,
        amount=Decimal("4176.00"),
        currency=CurrencyChoices.USD,
        method_type=PaymentMethodTypeChoices.CASH,
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    sales_debit, sales_credit, _, _ = service._process_current_sales([sr])

    # Assert
    assert _get_account_amount(sales_debit, setup_accounts["cash_foreign_account"]) == Decimal("4176.00")
    assert not _has_account(sales_credit, setup_accounts["igtf_perceived_payable_account"])


@pytest.mark.django_db
def test_id_hp_004_consolidacion_con_retenciones_iva_islr_soportadas(
    fiscal_profile, setup_accounts, sales_record_factory, vat_withholding_factory, islr_withholding_factory
):
    """[ID_HP_004] Validar acumulación de comprobantes de retención en activo por compensar."""
    # Arrange
    fiscal_profile.taxpayer_type = FiscalProfile.TaxpayerType.ORDINARY
    fiscal_profile.initial_fiscal_period.start_period = date(2026, 1, 1)
    fiscal_profile.save()

    sr = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.SERVICES,
        general_tax_base_16=Decimal("2000.00"),
        general_tax_debit_16=Decimal("320.00"),
        total_sales_inc_vat=Decimal("2320.00")
    )
    vat_withholding_factory(
        sales_record=sr,
        withheld_amount=Decimal("240.00")
    )
    islr_withholding_factory(
        sales_record=sr,
        retention_percentage=Decimal("2.00"),
        total_withheld_amount=Decimal("40.00")
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    sales_debit, sales_credit, _, _ = service._process_current_sales([sr])

    # Assert
    # DEBE
    assert _get_account_amount(sales_debit, setup_accounts["vat_withholdings_accumulated_account"]) == Decimal("240.00")
    assert _get_account_amount(sales_debit, setup_accounts["islr_withholdings_accumulated_account"]) == Decimal("40.00")
    assert _get_account_amount(sales_debit, setup_accounts["ar_commercial_national_account"]) == Decimal("2040.00")
    
    # HABER
    assert _get_account_amount(sales_credit, setup_accounts["taxable_services_sales_account"]) == Decimal("2000.00")
    assert _get_account_amount(sales_credit, setup_accounts["vat_debit_account"]) == Decimal("320.00")


@pytest.mark.django_db
def test_id_hp_005_omision_descargo_inventario_operaciones_servicios(
    fiscal_profile, sales_record_factory
):
    """[ID_HP_005] Confirmar exclusión de asientos de inventario en ventas exclusivas de servicios."""
    # Arrange
    sr1 = sales_record_factory(sale_category=SalesRecord.SaleCategory.SERVICES)
    sr2 = sales_record_factory(sale_category=SalesRecord.SaleCategory.SERVICES)
    sr3 = sales_record_factory(sale_category=SalesRecord.SaleCategory.SERVICES)

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    _, _, inv_debit, inv_credit = service._process_current_sales([sr1, sr2, sr3])

    # Assert
    assert inv_debit == []
    assert inv_credit == []


@pytest.mark.django_db
def test_id_hp_006_consolidacion_operaciones_mixtas_pagos_digitales(
    fiscal_profile, setup_accounts, sales_record_factory, customer_payment_factory
):
    """[ID_HP_006] Validar clasificación para facturas MIXED liquidadas bancariamente."""
    # Arrange
    sr = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.MIXED,
        goods_amount=Decimal("400.00"),
        services_amount=Decimal("600.00"),
        general_tax_base_16=Decimal("1000.00"),
        general_tax_debit_16=Decimal("160.00"),
        total_sales_inc_vat=Decimal("1160.00"),
    )
    customer_payment_factory(
        account_receivable=sr.account_receivable,
        amount=Decimal("1160.00"),
        currency=CurrencyChoices.VES,
        method_type=PaymentMethodTypeChoices.POS,
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    sales_debit, sales_credit, inv_debit, inv_credit = service._process_current_sales([sr])

    # Assert
    assert _get_account_amount(sales_debit, setup_accounts["bank_national_account"]) == Decimal("1160.00")
    assert _get_account_amount(sales_credit, setup_accounts["taxable_goods_sales_account"]) == Decimal("400.00")
    assert _get_account_amount(sales_credit, setup_accounts["taxable_services_sales_account"]) == Decimal("600.00")
    assert _get_account_amount(sales_credit, setup_accounts["vat_debit_account"]) == Decimal("160.00")
    assert _get_account_amount(inv_debit, setup_accounts["cogs_account"]) == Decimal("1.00")


@pytest.mark.django_db
def test_id_hp_007_consolidacion_facturas_multitasa(
    fiscal_profile, setup_accounts, sales_record_factory
):
    """[ID_HP_007] Validar sumatoria del débito fiscal total (16%, 8% y 31%)."""
    # Arrange
    sr = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.GOODS,
        general_tax_base_16=Decimal("1000.00"),
        general_tax_debit_16=Decimal("160.00"),
        reduced_tax_base_8=Decimal("500.00"),
        reduced_tax_debit_8=Decimal("40.00"),
        additional_tax_base_31=Decimal("1000.00"),
        additional_tax_debit_31=Decimal("310.00"),
        total_sales_inc_vat=Decimal("3010.00"),
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    _, sales_credit, _, _ = service._process_current_sales([sr])

    # Assert
    assert _get_account_amount(sales_credit, setup_accounts["vat_debit_account"]) == Decimal("510.00")


# ==============================================================================
# EDGE CASES (Casos Borde)
# ==============================================================================

@pytest.mark.django_db
def test_id_ec_001_procesamiento_lista_registros_vacia(fiscal_profile):
    """[ID_EC_001] Forzar consolidación sin registros para el período fiscal."""
    # Arrange
    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    sales_debit, sales_credit, inv_debit, inv_credit = service._process_current_sales([])

    # Assert
    assert sales_debit == []
    assert sales_credit == []
    assert inv_debit == []
    assert inv_credit == []


@pytest.mark.django_db
def test_id_ec_002_precision_decimal_estricta_redondeo_cuantificado(
    fiscal_profile, setup_accounts, sales_record_factory
):
    """[ID_EC_002] Evaluar aplicación obligatoria de `.quantize(Decimal('0.01'))`."""
    # Arrange
    sr = SalesRecord(
        sale_category=SalesRecord.SaleCategory.GOODS,
        general_tax_base_16=Decimal("333.333333"),
        general_tax_debit_16=Decimal("53.333333"),
        total_sales_inc_vat=Decimal("386.666666")
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    _, sales_credit, _, _ = service._process_current_sales([sr])

    # Assert
    assert _get_account_amount(sales_credit, setup_accounts["taxable_goods_sales_account"]) == Decimal("333.33")
    assert _get_account_amount(sales_credit, setup_accounts["vat_debit_account"]) == Decimal("53.33")


@pytest.mark.django_db
def test_id_ec_003_omision_cuentas_sumatoria_cero(
    fiscal_profile, setup_accounts, sales_record_factory
):
    """[ID_EC_003] Validar que no se generen tuplas de transacción con 0.00."""
    # Arrange
    sr = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.GOODS,
        general_tax_base_16=Decimal("100.00"),
        general_tax_debit_16=Decimal("16.00"),
        total_sales_inc_vat=Decimal("116.00")
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    sales_debit, sales_credit, _, _ = service._process_current_sales([sr])

    # Assert
    assert not _has_account(sales_debit, setup_accounts["cash_national_account"])
    assert not _has_account(sales_debit, setup_accounts["islr_withholdings_accumulated_account"])
    assert not _has_account(sales_credit, setup_accounts["exempt_goods_sales_account"])


@pytest.mark.django_db
def test_id_ec_008_ventas_exportacion_fob_y_operaciones_no_sujetas(
    fiscal_profile, setup_accounts, sales_record_factory
):
    """[ID_EC_008] Verificar agregación de operaciones FOB e internamente no sujetas."""
    # Arrange
    sr = sales_record_factory(
        sale_category=SalesRecord.SaleCategory.GOODS,
        sale_type=SalesRecord.SaleType.EXPORT,
        fob_export_value=Decimal("6000.00"),
        total_sales_inc_vat=Decimal("6000.00"),
        general_tax_base_16=Decimal("0.00"),
        general_tax_debit_16=Decimal("0.00")
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    _, sales_credit, _, _ = service._process_current_sales([sr])

    # Assert
    assert _get_account_amount(sales_credit, setup_accounts["exempt_goods_sales_account"]) == Decimal("6000.00")