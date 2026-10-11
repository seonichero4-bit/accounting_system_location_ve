"""Suite de pruebas unitarias para el servicio de totalización de ventas.

Este módulo implementa las pruebas correspondientes a la consolidación contable
de y notas de crédito (`_process_credit_notes`), validando la correcta generación de partidas para
el Libro Diario y el control de inventarios.
"""
from datetime import date
from decimal import Decimal
import pytest

from django.core.exceptions import ValidationError
from django_ledger.models import AccountModel

from data_access.models.base import FiscalProfile
from data_access.models.sales_record import SalesRecord
from data_access.models.customer_payment import CurrencyChoices, PaymentMethodTypeChoices
from data_access.models.credit_note_settlement import CreditNoteSettlement
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


@pytest.mark.django_db
def test_id_hp_001_devolucion_fisica_bienes_bolivares_saldo_favor(
    fiscal_profile, setup_accounts, sales_record_factory,
    sales_record_credit_note_factory
):
    """[ID_HP_001] Validar consolidación de Nota de Crédito por devolución en VES.
    
    Genera un reembolso parcial en efectivo y acredita el remanente al saldo a
    favor del cliente, reingresando el inventario.
    """
    # Arrange
    fiscal_profile.taxpayer_type = FiscalProfile.TaxpayerType.ORDINARY
    fiscal_profile.initial_fiscal_period.start_period = date(2026, 2, 1)
    fiscal_profile.save()

    sr_inv = sales_record_factory(
        total_sales_inc_vat=Decimal("1160.00"),
        general_tax_base_16=Decimal("1000.00"),
        general_tax_debit_16=Decimal("160.00")
    )
    
    sr_cn = sales_record_credit_note_factory(
        affected_invoice=sr_inv,
        sale_category=SalesRecord.SaleCategory.GOODS,
        total_sales_inc_vat=Decimal("1160.00"),
        general_tax_base_16=Decimal("1000.00"),
        general_tax_debit_16=Decimal("160.00")
    )

    # Inyección directa de datos asimétricos exigidos en el Test Plan eludiendo el .full_clean()
    CreditNoteSettlement.objects.create(
        fiscal_profile=fiscal_profile,
        sales_record=sr_cn,
        settlement_type=CreditNoteSettlement.SettlementType.RETURNS,
        currency=CurrencyChoices.VES,
        returned_goods_value=Decimal("1160.00"),
        cash_amount=Decimal("500.00"),
        customer_credit_balance_amount=Decimal("660.00"),
        refunded_amount=Decimal("1160.00"),
        fiscal_period=sr_cn.fiscal_period
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    cn_debit, cn_credit, inv_debit, inv_credit = service._process_credit_notes([sr_cn])

    # Assert
    # DEBE
    assert _get_account_amount(cn_debit, setup_accounts["goods_sales_returns_account"]) == Decimal("1000.00")
    assert _get_account_amount(cn_debit, setup_accounts["vat_debit_account"]) == Decimal("160.00")
    
    # HABER
    assert _get_account_amount(cn_credit, setup_accounts["cash_national_account"]) == Decimal("500.00")
    assert _get_account_amount(cn_credit, setup_accounts["customer_credit_balance_account"]) == Decimal("660.00")
    
    # INVENTARIO
    assert _get_account_amount(inv_debit, setup_accounts["inventory_account"]) == Decimal("1.00")
    assert _get_account_amount(inv_credit, setup_accounts["cogs_account"]) == Decimal("1.00")


@pytest.mark.django_db
def test_id_hp_002_reversion_igtf_percibido_spe_reembolso_divisas(
    fiscal_profile, setup_accounts, sales_record_factory,
    sales_record_credit_note_factory
):
    """[ID_HP_002] Verificar reversión de IGTF en DEBE y abono por reembolso divisas (SPE)."""
    # Arrange
    fiscal_profile.taxpayer_type = FiscalProfile.TaxpayerType.SPECIAL
    fiscal_profile.initial_fiscal_period.start_period = date(2026, 2, 15)
    fiscal_profile.save()

    sr_inv = sales_record_factory(
        total_sales_inc_vat=Decimal("1160.00"),
        general_tax_base_16=Decimal("1000.00"),
        general_tax_debit_16=Decimal("160.00")
    )
    sr_cn = sales_record_credit_note_factory(
        affected_invoice=sr_inv,
        sale_category=SalesRecord.SaleCategory.GOODS,
        total_sales_inc_vat=Decimal("1160.00"),
        general_tax_base_16=Decimal("1000.00"),
        general_tax_debit_16=Decimal("160.00"),
        igtf_tax_base=Decimal("1000.00"),
        igtf_tax_amount=Decimal("30.00")
    )

    CreditNoteSettlement.objects.create(
        fiscal_profile=fiscal_profile,
        sales_record=sr_cn,
        settlement_type=CreditNoteSettlement.SettlementType.RETURNS,
        currency=CurrencyChoices.USD,
        returned_goods_value=Decimal("1160.00"),
        cash_amount=Decimal("1190.00"),
        refunded_amount=Decimal("1190.00"),
        fiscal_period=sr_cn.fiscal_period
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    cn_debit, cn_credit, inv_debit, inv_credit = service._process_credit_notes([sr_cn])

    # Assert
    assert _get_account_amount(cn_debit, setup_accounts["goods_sales_returns_account"]) == Decimal("1000.00")
    assert _get_account_amount(cn_debit, setup_accounts["vat_debit_account"]) == Decimal("160.00")
    assert _get_account_amount(cn_debit, setup_accounts["igtf_perceived_payable_account"]) == Decimal("30.00")

    assert _get_account_amount(cn_credit, setup_accounts["cash_foreign_account"]) == Decimal("1190.00")
    
    assert _get_account_amount(inv_debit, setup_accounts["inventory_account"]) == Decimal("1.00")
    assert _get_account_amount(inv_credit, setup_accounts["cogs_account"]) == Decimal("1.00")


@pytest.mark.django_db
def test_id_hp_003_exclusion_reversion_igtf_ordinarios_divisas(
    fiscal_profile, setup_accounts, sales_record_factory,
    sales_record_credit_note_factory
):
    """[ID_HP_003] Confirmar exclusión de cuenta de IGTF en reversión para Ordinarios."""
    # Arrange
    fiscal_profile.taxpayer_type = FiscalProfile.TaxpayerType.ORDINARY
    fiscal_profile.initial_fiscal_period.start_period = date(2026, 2, 1)
    fiscal_profile.save()

    sr_inv = sales_record_factory(
        total_sales_inc_vat=Decimal("1160.00"),
        general_tax_base_16=Decimal("1000.00"),
        general_tax_debit_16=Decimal("160.00")
    )
    sr_cn = sales_record_credit_note_factory(
        affected_invoice=sr_inv,
        sale_category=SalesRecord.SaleCategory.GOODS,
        total_sales_inc_vat=Decimal("1160.00"),
        general_tax_base_16=Decimal("1000.00"),
        general_tax_debit_16=Decimal("160.00"),
        igtf_tax_base=Decimal("1000.00"),
        igtf_tax_amount=Decimal("30.00")  # Este valor debe ser ignorado lógicamente por ser Ordinario
    )

    CreditNoteSettlement.objects.create(
        fiscal_profile=fiscal_profile,
        sales_record=sr_cn,
        settlement_type=CreditNoteSettlement.SettlementType.RETURNS,
        currency=CurrencyChoices.USD,
        returned_goods_value=Decimal("1160.00"),
        cash_amount=Decimal("1160.00"),
        refunded_amount=Decimal("1160.00"),
        fiscal_period=sr_cn.fiscal_period
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    cn_debit, cn_credit, inv_debit, inv_credit = service._process_credit_notes([sr_cn])

    # Assert
    assert _get_account_amount(cn_debit, setup_accounts["goods_sales_returns_account"]) == Decimal("1000.00")
    assert _get_account_amount(cn_debit, setup_accounts["vat_debit_account"]) == Decimal("160.00")
    assert not _has_account(cn_debit, setup_accounts["igtf_perceived_payable_account"])

    assert _get_account_amount(cn_credit, setup_accounts["cash_foreign_account"]) == Decimal("1160.00")


@pytest.mark.django_db
def test_id_hp_004_nota_credito_financiera_descuento_comercial(
    fiscal_profile, setup_accounts, sales_record_factory,
    sales_record_credit_note_factory
):
    """[ID_HP_004] Validar procesamiento de NC financiera por descuentos (Sin Reingreso)."""
    # Arrange
    sr_inv = sales_record_factory(
        total_sales_inc_vat=Decimal("1000.00"),
        general_tax_base_16=Decimal("862.07"),
        general_tax_debit_16=Decimal("137.93")
    )
    sr_cn = sales_record_credit_note_factory(
        affected_invoice=sr_inv,
        sale_category=SalesRecord.SaleCategory.GOODS,
        total_sales_inc_vat=Decimal("580.00"),
        general_tax_base_16=Decimal("500.00"),
        general_tax_debit_16=Decimal("80.00")
    )

    CreditNoteSettlement.objects.create(
        fiscal_profile=fiscal_profile,
        sales_record=sr_cn,
        settlement_type=CreditNoteSettlement.SettlementType.DISCOUNTS,
        currency=CurrencyChoices.VES,
        commercial_discount_amount=Decimal("580.00"),
        refunded_amount=Decimal("0.00"),
        fiscal_period=sr_cn.fiscal_period
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    cn_debit, cn_credit, inv_debit, inv_credit = service._process_credit_notes([sr_cn])

    # Assert
    assert _get_account_amount(cn_debit, setup_accounts["sales_discount_account"]) == Decimal("500.00")
    assert _get_account_amount(cn_debit, setup_accounts["vat_debit_account"]) == Decimal("80.00")
    assert _get_account_amount(cn_credit, setup_accounts["ar_commercial_national_account"]) == Decimal("580.00")
    
    assert inv_debit == []
    assert inv_credit == []


@pytest.mark.django_db
def test_id_hp_005_reajuste_proporcional_retenciones_acumuladas_islr_iva(
    fiscal_profile, setup_accounts, sales_record_factory,
    sales_record_credit_note_factory, vat_withholding_factory, islr_withholding_factory
):
    """[ID_HP_005] Verificar que los reajustes por retenciones se abonen al activo."""
    # Arrange
    sr_inv = sales_record_factory(
        total_sales_inc_vat=Decimal("1000.00"),
        general_tax_base_16=Decimal("862.07"),
        general_tax_debit_16=Decimal("137.93")
    )
    sr_cn = sales_record_credit_note_factory(
        affected_invoice=sr_inv,
        sale_category=SalesRecord.SaleCategory.SERVICES,
        total_sales_inc_vat=Decimal("580.00"),
        general_tax_base_16=Decimal("500.00"),
        general_tax_debit_16=Decimal("80.00")
    )

    vat_withholding_factory(sales_record=sr_cn, withheld_amount=Decimal("60.00"))
    islr_withholding_factory(sales_record=sr_cn, total_withheld_amount=Decimal("10.00"), subtracting=Decimal("5.00"))

    CreditNoteSettlement.objects.create(
        fiscal_profile=fiscal_profile,
        sales_record=sr_cn,
        settlement_type=CreditNoteSettlement.SettlementType.DISCOUNTS,
        currency=CurrencyChoices.VES,
        commercial_discount_amount=Decimal("580.00"),
        refunded_amount=Decimal("0.00"),
        fiscal_period=sr_cn.fiscal_period
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    cn_debit, cn_credit, inv_debit, inv_credit = service._process_credit_notes([sr_cn])

    # Assert
    assert _get_account_amount(cn_debit, setup_accounts["services_discounts_account"]) == Decimal("500.00")
    assert _get_account_amount(cn_debit, setup_accounts["vat_debit_account"]) == Decimal("80.00")
    
    assert _get_account_amount(cn_credit, setup_accounts["vat_withholdings_accumulated_account"]) == Decimal("60.00")
    assert _get_account_amount(cn_credit, setup_accounts["islr_withholdings_accumulated_account"]) == Decimal("10.00")
    assert _get_account_amount(cn_credit, setup_accounts["ar_commercial_national_account"]) == Decimal("510.00")
    
    assert inv_debit == []
    assert inv_credit == []


@pytest.mark.django_db
def test_id_hp_006_consolidacion_liquidacion_mixta_bancarizada(
    fiscal_profile, setup_accounts, sales_record_factory,
    sales_record_credit_note_factory
):
    """[ID_HP_006] Validar consolidación de NC MIXED con reembolsos mixtos bancarizados."""
    # Arrange
    sr_inv = sales_record_factory(
        total_sales_inc_vat=Decimal("1000.00"),
        general_tax_base_16=Decimal("862.07"),
        general_tax_debit_16=Decimal("137.93")
    )
    sr_cn = sales_record_credit_note_factory(
        affected_invoice=sr_inv,
        sale_category=SalesRecord.SaleCategory.MIXED,
        total_sales_inc_vat=Decimal("696.00"),
        general_tax_base_16=Decimal("600.00"),
        general_tax_debit_16=Decimal("96.00"),
        goods_amount=Decimal("431.03"),
        services_amount=Decimal("168.97")
    )

    CreditNoteSettlement.objects.create(
        fiscal_profile=fiscal_profile,
        sales_record=sr_cn,
        settlement_type=CreditNoteSettlement.SettlementType.MIXED,
        currency=CurrencyChoices.VES,
        returned_goods_value=Decimal("500.00"),
        commercial_discount_amount=Decimal("196.00"),
        bank_transfer_amount=Decimal("300.00"),
        mobile_payment_amount=Decimal("200.00"),
        refunded_amount=Decimal("500.00"),
        payment_reference="REF-987654",
        fiscal_period=sr_cn.fiscal_period
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    cn_debit, cn_credit, inv_debit, inv_credit = service._process_credit_notes([sr_cn])

    # Assert
    assert _get_account_amount(cn_debit, setup_accounts["goods_sales_returns_account"]) == Decimal("431.03")
    assert _get_account_amount(cn_debit, setup_accounts["sales_discount_account"]) == Decimal("168.97")
    assert _get_account_amount(cn_debit, setup_accounts["vat_debit_account"]) == Decimal("96.00")
    
    assert _get_account_amount(cn_credit, setup_accounts["bank_national_account"]) == Decimal("500.00")
    assert _get_account_amount(cn_credit, setup_accounts["ar_commercial_national_account"]) == Decimal("196.00")
    
    assert _get_account_amount(inv_debit, setup_accounts["inventory_account"]) == Decimal("1.00")
    assert _get_account_amount(inv_credit, setup_accounts["cogs_account"]) == Decimal("1.00")


@pytest.mark.django_db
def test_id_ec_001_procesamiento_lista_notas_credito_vacia(fiscal_profile):
    """[ID_EC_001] Evaluar retorno seguro de tuplas vacías ante lista vacía."""
    # Arrange
    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    cn_debit, cn_credit, inv_debit, inv_credit = service._process_credit_notes([])

    # Assert
    assert cn_debit == []
    assert cn_credit == []
    assert inv_debit == []
    assert inv_credit == []


@pytest.mark.django_db
def test_id_ec_002_precision_decimal_estricta_redondeo_cuantificado_cn(
    fiscal_profile, setup_accounts, sales_record_factory,
    sales_record_credit_note_factory
):
    """[ID_EC_002] Comprobar cuantificación estricta en agregados de notas de crédito."""
    # Arrange
    sr_inv = sales_record_factory(
        total_sales_inc_vat=Decimal("154.67"),
        general_tax_base_16=Decimal("133.34"),
        general_tax_debit_16=Decimal("21.33")
    )
    sr_cn = sales_record_credit_note_factory(
        affected_invoice=sr_inv,
        sale_category=SalesRecord.SaleCategory.GOODS,
        general_tax_base_16=Decimal("133.33"),
        general_tax_debit_16=Decimal("21.33"),
        total_sales_inc_vat=Decimal("154.66")
    )

    CreditNoteSettlement.objects.create(
        fiscal_profile=fiscal_profile,
        sales_record=sr_cn,
        settlement_type=CreditNoteSettlement.SettlementType.RETURNS,
        currency=CurrencyChoices.VES,
        returned_goods_value=Decimal("154.66"),
        fiscal_period=sr_cn.fiscal_period
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    cn_debit, _, _, _ = service._process_credit_notes([sr_cn])

    # Assert
    assert _get_account_amount(cn_debit, setup_accounts["goods_sales_returns_account"]) == Decimal("133.33")
    assert _get_account_amount(cn_debit, setup_accounts["vat_debit_account"]) == Decimal("21.33")


@pytest.mark.django_db
def test_id_ec_003_omision_cuentas_sumatoria_cero_cn(
    fiscal_profile, setup_accounts, sales_record_factory,
    sales_record_credit_note_factory
):
    """[ID_EC_003] Verificar exclusión absoluta de transacciones con monto 0.00."""
    # Arrange
    sr_inv = sales_record_factory(
        total_sales_inc_vat=Decimal("100.00"),
        exempt_internal_sales=Decimal("100.00"),
        general_tax_base_16=Decimal("0.00"),
        general_tax_debit_16=Decimal("0.00")
    )
    sr_cn = sales_record_credit_note_factory(
        affected_invoice=sr_inv,
        sale_category=SalesRecord.SaleCategory.GOODS,
        total_sales_inc_vat=Decimal("100.00"),
        exempt_internal_sales=Decimal("100.00"),
        general_tax_base_16=Decimal("0.00"),
        general_tax_debit_16=Decimal("0.00")
    )

    CreditNoteSettlement.objects.create(
        fiscal_profile=fiscal_profile,
        sales_record=sr_cn,
        settlement_type=CreditNoteSettlement.SettlementType.DISCOUNTS,
        currency=CurrencyChoices.VES,
        commercial_discount_amount=Decimal("100.00"),
        fiscal_period=sr_cn.fiscal_period
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    cn_debit, cn_credit, _, _ = service._process_credit_notes([sr_cn])

    # Assert
    assert not _has_account(cn_debit, setup_accounts["goods_sales_returns_account"])
    assert not _has_account(cn_credit, setup_accounts["cash_national_account"])


@pytest.mark.django_db
def test_id_ec_004_lanzamiento_excepcion_ausencia_liquidacion_operativa(
    fiscal_profile, sales_record_factory, sales_record_credit_note_factory
):
    """[ID_EC_004] Comprobar lanzamiento de excepción por ausencia de settlement."""
    # Arrange
    sr_inv = sales_record_factory(
        total_sales_inc_vat=Decimal("100.00"),
        exempt_internal_sales=Decimal("100.00"),
        general_tax_base_16=Decimal("0.00"),
        general_tax_debit_16=Decimal("0.00")
    )
    sr_cn = sales_record_credit_note_factory(
        affected_invoice=sr_inv,
        control_number="00-00001234",
        total_sales_inc_vat=Decimal("100.00"),
        exempt_internal_sales=Decimal("100.00")
    )
    # Intencionadamente no se asocia ninguna instancia de CreditNoteSettlement

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act & Assert
    with pytest.raises(
        ValidationError,
        match=r"La nota de crédito con N° de Control '00-00001234' no posee una liquidación operativa"
    ):
        service._process_credit_notes([sr_cn])


# @pytest.mark.django_db
# def test_id_ec_005_exclusion_reversion_igtf_contribuyente_ordinario(
#     fiscal_profile, setup_accounts, sales_record_factory,
#     sales_record_credit_note_factory
# ):
#     """[ID_EC_005] Evaluar exclusión de reversión de IGTF en contribuyente ORDINARY con IGTF positivo."""
#     # Arrange
#     fiscal_profile.taxpayer_type = FiscalProfile.TaxpayerType.ORDINARY
#     fiscal_profile.initial_fiscal_period.start_period = date(2026, 2, 1)
#     fiscal_profile.save()

#     sr_inv = sales_record_factory(
#         total_sales_inc_vat=Decimal("1160.00"),
#         general_tax_base_16=Decimal("1000.00"),
#         general_tax_debit_16=Decimal("160.00")
#     )
#     sr_cn = sales_record_credit_note_factory(
#         affected_invoice=sr_inv,
#         sale_category=SalesRecord.SaleCategory.GOODS,
#         total_sales_inc_vat=Decimal("1160.00"),
#         general_tax_base_16=Decimal("1000.00"),
#         general_tax_debit_16=Decimal("160.00"),
#         igtf_tax_base=Decimal("1000.00"),
#         igtf_tax_amount=Decimal("30.00")
#     )

#     CreditNoteSettlement.objects.create(
#         fiscal_profile=fiscal_profile,
#         sales_record=sr_cn,
#         settlement_type=CreditNoteSettlement.SettlementType.RETURNS,
#         currency=CurrencyChoices.USD,
#         returned_goods_value=Decimal("1160.00"),
#         cash_amount=Decimal("1160.00"),
#         refunded_amount=Decimal("1160.00"),
#         fiscal_period=sr_cn.fiscal_period
#     )

#     service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

#     # Act
#     cn_debit, cn_credit, inv_debit, inv_credit = service._process_credit_notes([sr_cn])

#     # Assert
#     assert _get_account_amount(cn_debit, setup_accounts["goods_sales_returns_account"]) == Decimal("1000.00")
#     assert _get_account_amount(cn_debit, setup_accounts["vat_debit_account"]) == Decimal("160.00")
#     assert not _has_account(cn_debit, setup_accounts["igtf_perceived_payable_account"])
#     assert _get_account_amount(cn_credit, setup_accounts["cash_foreign_account"]) == Decimal("1160.00")


@pytest.mark.django_db
def test_id_ec_006_consolidacion_notas_credito_multitasa(
    fiscal_profile, setup_accounts, sales_record_factory,
    sales_record_credit_note_factory
):
    """[ID_EC_006] Validar cuantificación de reversiones de IVA multitasa."""
    # Arrange
    sr_inv = sales_record_factory(
        total_sales_inc_vat=Decimal("2339.00"),
        exempt_internal_sales=Decimal("200.00"),
        general_tax_base_16=Decimal("1000.00"),
        general_tax_debit_16=Decimal("160.00"),
        reduced_tax_base_8=Decimal("300.00"),
        reduced_tax_debit_8=Decimal("24.00"),
        additional_tax_base_31=Decimal("500.00"),
        additional_tax_debit_31=Decimal("155.00")
    )
    sr_cn = sales_record_credit_note_factory(
        affected_invoice=sr_inv,
        sale_category=SalesRecord.SaleCategory.GOODS,
        total_sales_inc_vat=Decimal("2339.00"),
        exempt_internal_sales=Decimal("200.00"),
        general_tax_base_16=Decimal("1000.00"),
        general_tax_debit_16=Decimal("160.00"),
        reduced_tax_base_8=Decimal("300.00"),
        reduced_tax_debit_8=Decimal("24.00"),
        additional_tax_base_31=Decimal("500.00"),
        additional_tax_debit_31=Decimal("155.00")
    )

    CreditNoteSettlement.objects.create(
        fiscal_profile=fiscal_profile,
        sales_record=sr_cn,
        settlement_type=CreditNoteSettlement.SettlementType.RETURNS,
        currency=CurrencyChoices.VES,
        returned_goods_value=Decimal("2339.00"),
        fiscal_period=sr_cn.fiscal_period
    )

    service = SalesAccountingTotalizationService(fiscal_profile, "2026-09")

    # Act
    cn_debit, cn_credit, _, _ = service._process_credit_notes([sr_cn])

    # Assert
    # 160.00 + 24.00 + 155.00 = 339.00
    assert _get_account_amount(cn_debit, setup_accounts["vat_debit_account"]) == Decimal("339.00")
    
    # 2339.00 de total ar amortizado (2339-339=2000 en devoluciones)
    assert _get_account_amount(cn_debit, setup_accounts["goods_sales_returns_account"]) == Decimal("2000.00")
    assert _get_account_amount(cn_credit, setup_accounts["ar_commercial_national_account"]) == Decimal("2339.00")