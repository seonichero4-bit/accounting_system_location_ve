"""Módulo de configuración de fixtures para la suite de pruebas.

Este archivo contiene las fixtures base predefinidas y los patrones Factory
para instanciar los modelos de la aplicación garantizando la validez de los
datos fiscales y contables.
"""

from datetime import date
from decimal import Decimal
import pytest
from django.contrib.auth.models import User
from django_ledger.io import roles
from django_ledger.models import LedgerModel

from business_logic.services.fiscal_profile_service import FiscalProfileService
from data_access.models.base import FiscalProfile
from data_access.models.fiscalperiod import FiscalPeriod
from data_access.models.customer import Customer
from data_access.models.sales_record import SalesRecord
from data_access.models.account_receivable import AccountReceivable
from data_access.models.vat_withholding_sales import VatWithHolding
from data_access.models.islr_withholding_sales import IslrWithHolding
from data_access.models.customer_payment import (
    CustomerPayment,
    PaymentMethodTypeChoices,
    CurrencyChoices,
)
from data_access.models.payment_imputation import PaymentImputation
from data_access.models.credit_note_settlement import CreditNoteSettlement


@pytest.fixture
def admin_user(db) -> User:
    """Instancia el usuario administrador requerido para la creación de la entidad."""
    return User.objects.create_superuser(
        username="admin_test",
        email="admin@test.com",
        password="password123"
    )


@pytest.fixture
def fiscal_profile(db, admin_user) -> FiscalProfile:
    """Crea el perfil fiscal multi-tenant mediante el servicio FiscalProfileService."""
    service = FiscalProfileService(admin_user=admin_user)
    return service.create_fiscal_profile(
        entity_name="Empresa de Prueba C.A.",
        use_accrual_method=True,
        fy_start_month=1,
        rif="J123456789",
        taxpayer_type="SPECIAL",
        start_period=date(2026, 1, 15)
    )


@pytest.fixture
def ledger_model(db, fiscal_profile) -> LedgerModel:
    """Instancia el Libro Mayor General vía ORM vinculándolo a la entidad."""
    ledger = LedgerModel.objects.create(
        name="Libro Mayor General",
        entity=fiscal_profile.entity
    )
    fiscal_profile.ledger = ledger
    fiscal_profile.save()
    return ledger


@pytest.fixture
def chart_of_accounts(db, fiscal_profile):
    """Genera el Plan de Cuentas base asociado a la entidad del perfil fiscal."""
    return fiscal_profile.entity.create_chart_of_accounts(
        coa_name="Plan de Cuentas Matriz",
        assign_as_default=True,
        commit=True
    )


@pytest.fixture
def setup_accounts(db, fiscal_profile, chart_of_accounts, ledger_model) -> dict:
    """Instancia las cuentas contables preconfiguradas y asigna las cuentas de control al FiscalProfile."""

    accounts_config = [
        # 1. Cuentas de Ingresos (Ventas y Recargos) - Haber / Credit
        {
            "attr": "taxable_goods_sales_account",
            "code": "41101",
            "name": "Ventas de Bienes Muebles Gravadas",
            "role": roles.INCOME_OPERATIONAL,
            "balance_type": "credit",
        },
        {
            "attr": "taxable_services_sales_account",
            "code": "41102",
            "name": "Ingresos por Servicios Prestados Gravados",
            "role": roles.INCOME_OPERATIONAL,
            "balance_type": "credit",
        },
        {
            "attr": "exempt_goods_sales_account",
            "code": "41103",
            "name": "Ventas de Bienes Exentos o Exonerados",
            "role": roles.INCOME_OPERATIONAL,
            "balance_type": "credit",
        },
        {
            "attr": "exempt_services_sales_account",
            "code": "41104",
            "name": "Ingresos por Servicios Prestados Exentos o Exonerados",
            "role": roles.INCOME_OPERATIONAL,
            "balance_type": "credit",
        },
        {
            "attr": "sales_surcharges_account",
            "code": "41105",
            "name": "Aumentos de Precio y Recargos en Ventas",
            "role": roles.INCOME_OPERATIONAL,
            "balance_type": "credit",
        },
        {
            "attr": "services_surcharges_account",
            "code": "41106",
            "name": "Aumentos de Precio y Recargos en Servicios",
            "role": roles.INCOME_OPERATIONAL,
            "balance_type": "credit",
        },
        # 2. Devoluciones, Rebajas y Descuentos en Ventas (Contra-Ingresos) - Debe / Debit
        {
            "attr": "goods_sales_returns_account",
            "code": "42101",
            "name": "Devoluciones en Ventas de Bienes",
            "role": roles.INCOME_OPERATIONAL,
            "balance_type": "debit",
        },
        {
            "attr": "goods_sales_allowances_account",
            "code": "42102",
            "name": "Rebajas en Ventas de Bienes",
            "role": roles.INCOME_OPERATIONAL,
            "balance_type": "debit",
        },
        {
            "attr": "services_discounts_account",
            "code": "42103",
            "name": "Ajustes y Descuentos en Ingresos por Servicios",
            "role": roles.INCOME_OPERATIONAL,
            "balance_type": "debit",
        },
        # 3. Cuentas de Pasivo (Impuestos por Enterar / Débitos Fiscales) - Haber / Credit
        {
            "attr": "vat_debit_account",
            "code": "21201",
            "name": "Débito Fiscal IVA",
            "role": roles.LIABILITY_CL_TAXES_PAYABLE,
            "balance_type": "credit",
        },
        {
            "attr": "igtf_perceived_payable_account",
            "code": "21202",
            "name": "IGTF Percibido por Enterar",
            "role": roles.LIABILITY_CL_TAXES_PAYABLE,
            "balance_type": "credit",
        },
        # 4. Cuentas de Activo (Retenciones Soportadas en Ventas) - Debe / Debit
        {
            "attr": "vat_withholdings_accumulated_account",
            "code": "11301",
            "name": "Retenciones de IVA Acumuladas por Compensar",
            "role": roles.ASSET_CA_PREPAID,
            "balance_type": "debit",
        },
        {
            "attr": "islr_withholdings_accumulated_account",
            "code": "11302",
            "name": "Retenciones de ISLR Acumuladas por Compensar",
            "role": roles.ASSET_CA_PREPAID,
            "balance_type": "debit",
        },
        # 5. Cuentas de Cobro y Cuentas por Cobrar (Tesorería y Clientes) - Debe / Debit
        {
            "attr": "cash_national_account",
            "code": "11101",
            "name": "Caja Moneda Nacional",
            "role": roles.ASSET_CA_CASH,
            "balance_type": "debit",
        },
        {
            "attr": "cash_foreign_account",
            "code": "11102",
            "name": "Caja Moneda Extranjera",
            "role": roles.ASSET_CA_CASH,
            "balance_type": "debit",
        },
        {
            "attr": "bank_national_account",
            "code": "11103",
            "name": "Banco Nacional",
            "role": roles.ASSET_CA_CASH,
            "balance_type": "debit",
        },
        {
            "attr": "bank_foreign_account",
            "code": "11104",
            "name": "Banco Moneda Extranjera",
            "role": roles.ASSET_CA_CASH,
            "balance_type": "debit",
        },
        {
            "attr": "ar_commercial_national_account",
            "code": "11201",
            "name": "Cuentas por Cobrar Comerciales (Nacional)",
            "role": roles.ASSET_CA_RECEIVABLES,
            "balance_type": "debit",
        },
        {
            "attr": "ar_commercial_foreign_account",
            "code": "11202",
            "name": "Cuentas por Cobrar Comerciales (Extranjera)",
            "role": roles.ASSET_CA_RECEIVABLES,
            "balance_type": "debit",
        },
        # 6. Cuentas de Costo e Inventario - Debe / Debit
        {
            "attr": "cogs_account",
            "code": "51101",
            "name": "Costo de Ventas",
            "role": roles.COGS,
            "balance_type": "debit",
        },
        {
            "attr": "inventory_account",
            "code": "11401",
            "name": "Inventario de Mercancías",
            "role": roles.ASSET_CA_INVENTORY,
            "balance_type": "debit",
        },
    ]

    created_accounts = {}

    for cfg in accounts_config:
        account_instance = fiscal_profile.entity.create_account(
            coa_model=chart_of_accounts,
            code=cfg["code"],
            name=cfg["name"],
            role=cfg["role"],
            balance_type=cfg["balance_type"],
            active=True,
        )
        setattr(fiscal_profile, cfg["attr"], account_instance)
        created_accounts[cfg["attr"]] = account_instance

    fiscal_profile.save()
    return created_accounts


# ==============================================================================
# FACTORIES Y FIXTURES DE MODELOS DE NÚCLEO Y VENTAS
# ==============================================================================

@pytest.fixture
def customer_factory(db, fiscal_profile):
    """Factory fixture para generar instancias del modelo Customer."""
    def _create_customer(**kwargs):
        count = Customer.objects.count() + 1
        defaults = {
            "fiscal_profile": fiscal_profile,
            "rif": f"J{count:08d}0",
            "name": f"Cliente de Prueba {count} C.A.",
            "fiscal_address": "Av. Principal con Calle Comercio, Edif. Centro, Caracas",
            "phone_number": "02125550000",
            "taxpayer_type": Customer.TaxpayerType.ORDINARY,
        }
        defaults.update(kwargs)
        customer = Customer(**defaults)
        customer.full_clean()
        customer.save()
        return customer

    return _create_customer


@pytest.fixture
def customer(customer_factory) -> Customer:
    """Fixture básica que retorna un Customer por defecto."""
    return customer_factory()


@pytest.fixture
def sales_record_factory(db, fiscal_profile, customer):
    """Factory fixture para construir registros en el Libro de Ventas (SalesRecord)."""
    def _create_sales_record(**kwargs):
        count = SalesRecord.objects.count() + 1
        client_inst = kwargs.pop("client", customer)

        defaults = {
            "fiscal_profile": fiscal_profile,
            "client": client_inst,
            "document_date": date(2026, 1, 15),
            "fiscal_period": date(2026, 1, 1),
            "document_type": SalesRecord.DocumentType.INVOICE,
            "document_number": f"FAC-{count:04d}",
            "control_number": f"00-{count:06d}",
            "sale_category": SalesRecord.SaleCategory.GOODS,
            "transaction_type": SalesRecord.TransactionType.REGISTER,
            "sale_type": SalesRecord.SaleType.INTERNAL,
            "record_status": SalesRecord.RecordStatus.PRELIMINARY,
            "general_tax_base_16": Decimal("100.00"),
            "general_tax_debit_16": Decimal("16.00"),
            "total_sales_inc_vat": Decimal("116.00"),
        }
        defaults.update(kwargs)
        record = SalesRecord(**defaults)
        record.full_clean()
        # El método save() genera automáticamente la AccountReceivable cuando document_type == INVOICE
        record.save()
        return record

    return _create_sales_record


@pytest.fixture
def sales_record_invoice(sales_record_factory) -> SalesRecord:
    """Fixture que crea una factura de venta (INVOICE) básica."""
    return sales_record_factory()


@pytest.fixture
def sales_record_credit_note_factory(db, fiscal_profile, sales_record_invoice):
    """Factory fixture para construir Notas de Crédito fiscales asociadas a facturas."""
    def _create_credit_note(affected_invoice=None, **kwargs):
        inv = affected_invoice or sales_record_invoice
        count = SalesRecord.objects.count() + 1

        defaults = {
            "fiscal_profile": inv.fiscal_profile,
            "client": inv.client,
            "document_date": inv.document_date,
            "fiscal_period": inv.fiscal_period,
            "document_type": SalesRecord.DocumentType.CREDIT_NOTE,
            "affected_invoice": inv,
            "document_number": f"NC-{count:04d}",
            "control_number": f"00-{count + 1000:06d}",
            "sale_category": inv.sale_category,
            "transaction_type": SalesRecord.TransactionType.REGISTER,
            "sale_type": SalesRecord.SaleType.INTERNAL,
            "record_status": SalesRecord.RecordStatus.PRELIMINARY,
            "general_tax_base_16": inv.general_tax_base_16,
            "general_tax_debit_16": inv.general_tax_debit_16,
            "total_sales_inc_vat": inv.total_sales_inc_vat,
        }
        defaults.update(kwargs)
        nc = SalesRecord(**defaults)
        nc.full_clean()
        nc.save()
        return nc

    return _create_credit_note


@pytest.fixture
def sales_record_credit_note(sales_record_credit_note_factory) -> SalesRecord:
    """Fixture que retorna una Nota de Crédito por defecto."""
    return sales_record_credit_note_factory()


@pytest.fixture
def sales_record_debit_note_factory(db, fiscal_profile, sales_record_invoice):
    """Factory fixture para construir Notas de Débito fiscales asociadas a facturas."""
    def _create_debit_note(affected_invoice=None, **kwargs):
        inv = affected_invoice or sales_record_invoice
        count = SalesRecord.objects.count() + 1

        defaults = {
            "fiscal_profile": inv.fiscal_profile,
            "client": inv.client,
            "document_date": inv.document_date,
            "fiscal_period": inv.fiscal_period,
            "document_type": SalesRecord.DocumentType.DEBIT_NOTE,
            "affected_invoice": inv,
            "document_number": f"ND-{count:04d}",
            "control_number": f"00-{count + 2000:06d}",
            "sale_category": inv.sale_category,
            "transaction_type": SalesRecord.TransactionType.REGISTER,
            "sale_type": SalesRecord.SaleType.INTERNAL,
            "record_status": SalesRecord.RecordStatus.PRELIMINARY,
            # Por defecto representa un recargo/ajuste adicional (ej. base de 20.00 + IVA 3.20 = 23.20)
            "general_tax_base_16": Decimal("20.00"),
            "general_tax_debit_16": Decimal("3.20"),
            "total_sales_inc_vat": Decimal("23.20"),
        }
        defaults.update(kwargs)
        nd = SalesRecord(**defaults)
        nd.full_clean()
        nd.save()
        return nd

    return _create_debit_note


@pytest.fixture
def sales_record_debit_note(sales_record_debit_note_factory) -> SalesRecord:
    """Fixture que retorna una Nota de Débito por defecto."""
    return sales_record_debit_note_factory()


@pytest.fixture
def account_receivable_factory(sales_record_factory):
    """Factory fixture para obtener la AccountReceivable instanciada mediante SalesRecord."""
    def _get_or_create_account_receivable(**sales_record_kwargs):
        sales_record_kwargs.setdefault("document_type", SalesRecord.DocumentType.INVOICE)
        record = sales_record_factory(**sales_record_kwargs)
        return record.account_receivable

    return _get_or_create_account_receivable


@pytest.fixture
def account_receivable(sales_record_invoice) -> AccountReceivable:
    """Fixture que retorna la Cuenta por Cobrar generada por la factura predeterminada."""
    return sales_record_invoice.account_receivable


# ==============================================================================
# FACTORIES Y FIXTURES DE RETENCIONES FISCALES
# ==============================================================================

@pytest.fixture
def vat_withholding_factory(db, fiscal_profile, sales_record_invoice):
    """Factory fixture para comprobantes de retención de IVA (VatWithHolding)."""
    def _create_vat_withholding(sales_record=None, **kwargs):
        doc = sales_record or sales_record_invoice
        count = VatWithHolding.objects.count() + 1
        issue_date = kwargs.get("issue_date", doc.document_date)
        prefix = issue_date.strftime("%Y%m")
        voucher_number = f"{prefix}{count:08d}"

        defaults = {
            "fiscal_profile": doc.fiscal_profile,
            "client": doc.client,
            "document": doc,
            "voucher_number": voucher_number,
            "issue_date": issue_date,
            "fiscal_period": doc.fiscal_period or date(2026, 1, 1),
            "client_name": doc.client.name,
            "client_rif": doc.client.rif,
            "document_number": doc.document_number or "FAC-0001",
            "control_number": doc.control_number or "00-000001",
            "total_amount": doc.total_sales_inc_vat,
            "tax_base": doc.general_tax_base_16,
            "tax_caused": doc.general_tax_debit_16,
            "withheld_amount": (doc.general_tax_debit_16 * Decimal("0.75")).quantize(Decimal("0.01")),
        }
        defaults.update(kwargs)
        withholding = VatWithHolding(**defaults)
        withholding.full_clean()
        withholding.save()
        return withholding

    return _create_vat_withholding


@pytest.fixture
def vat_withholding(vat_withholding_factory) -> VatWithHolding:
    """Fixture básica de comprobante de retención de IVA."""
    return vat_withholding_factory()


@pytest.fixture
def islr_withholding_factory(db, fiscal_profile, sales_record_invoice):
    """Factory fixture para comprobantes de retención de ISLR (IslrWithHolding)."""
    def _create_islr_withholding(sales_record=None, **kwargs):
        doc = sales_record or sales_record_invoice
        count = IslrWithHolding.objects.count() + 1
        gross = kwargs.get("gross_amount", doc.total_sales_inc_vat)
        tax_base = kwargs.get("tax_base", doc.general_tax_base_16 if doc.general_tax_base_16 > Decimal("0.00") else gross)
        pct = kwargs.get("retention_percentage", Decimal("3.00"))
        sub = kwargs.get("subtracting", Decimal("0.00"))
        tot_withheld = kwargs.get("total_withheld_amount", (tax_base * (pct / Decimal("100.00"))) - sub)
        net_pay = kwargs.get("net_amount_to_pay", gross - tot_withheld)

        defaults = {
            "fiscal_profile": doc.fiscal_profile,
            "client": doc.client,
            "document": doc,
            "voucher_number": f"ISLR-{count:06d}",
            "issue_date": doc.document_date,
            "fiscal_period": doc.fiscal_period or date(2026, 1, 1),
            "client_name": doc.client.name,
            "client_rif": doc.client.rif,
            "document_number": doc.document_number or "FAC-0001",
            "control_number": doc.control_number or "00-000001",
            "document_date": doc.document_date,
            "seniat_code": "001",
            "gross_amount": gross,
            "tax_base": tax_base,
            "retention_percentage": pct,
            "subtracting": sub,
            "total_withheld_amount": tot_withheld,
            "net_amount_to_pay": net_pay,
        }
        defaults.update(kwargs)
        withholding = IslrWithHolding(**defaults)
        withholding.full_clean()
        withholding.save()
        return withholding

    return _create_islr_withholding


@pytest.fixture
def islr_withholding(islr_withholding_factory) -> IslrWithHolding:
    """Fixture básica de comprobante de retención de ISLR."""
    return islr_withholding_factory()


# ==============================================================================
# FACTORIES Y FIXTURES DE TESORERÍA, IMPUTACIÓN Y LIQUIDACIONES
# ==============================================================================

@pytest.fixture
def customer_payment_factory(db, fiscal_profile, customer, account_receivable):
    """Factory fixture para pagos de clientes (CustomerPayment) e Imputación asociada."""
    def _create_customer_payment(**kwargs):
        cxc = kwargs.pop("account_receivable", account_receivable)
        amount = kwargs.pop("amount", cxc.net_receivable_balance)

        payment_defaults = {
            "fiscal_profile": fiscal_profile,
            "customer": cxc.sales_record.client if cxc else customer,
            "fiscal_period": date(2026, 1, 1),
            "payment_date": date(2026, 1, 15),
            "method_type": PaymentMethodTypeChoices.BANK_TRANSFER,
            "currency": CurrencyChoices.VES,
            "nominal_value": amount,
            "exchange_rate": Decimal("1.0000"),
            "total_amount": amount,
            "reference": "TR-123456",
        }
        payment_defaults.update(kwargs)

        payment = CustomerPayment(**payment_defaults)
        payment.save()

        # Vinculación de Imputación para cumplir con la validación de total_amount en clean()
        PaymentImputation.objects.create(
            fiscal_profile=payment.fiscal_profile,
            payment=payment,
            account_receivable=cxc,
            fiscal_period=payment.fiscal_period,
            imputed_amount=amount,
        )

        payment.full_clean()
        return payment

    return _create_customer_payment


@pytest.fixture
def customer_payment(customer_payment_factory) -> CustomerPayment:
    """Fixture básica de un pago procesado con su imputación."""
    return customer_payment_factory()


@pytest.fixture
def payment_imputation_factory(db, fiscal_profile, customer_payment, account_receivable):
    """Factory fixture para generar instancias individuales de PaymentImputation."""
    def _create_imputation(**kwargs):
        defaults = {
            "fiscal_profile": fiscal_profile,
            "payment": customer_payment,
            "account_receivable": account_receivable,
            "fiscal_period": date(2026, 1, 1),
            "imputed_amount": customer_payment.total_amount,
        }
        defaults.update(kwargs)
        imputation = PaymentImputation(**defaults)
        imputation.full_clean()
        imputation.save()
        return imputation

    return _create_imputation


@pytest.fixture
def payment_imputation(customer_payment) -> PaymentImputation:
    """Fixture que devuelve la imputación generada automáticamente con el pago por defecto."""
    return customer_payment.imputations.first()


@pytest.fixture
def credit_note_settlement_factory(db, fiscal_profile, sales_record_credit_note):
    """Factory fixture para la liquidación operativa/financiera de Notas de Crédito."""
    def _create_settlement(credit_note=None, **kwargs):
        nc = credit_note or sales_record_credit_note
        defaults = {
            "fiscal_profile": nc.fiscal_profile,
            "sales_record": nc,
            "settlement_type": CreditNoteSettlement.SettlementType.RETURNS,
            "returned_goods_value": nc.total_sales_inc_vat,
            "reimbursement_in_services": Decimal("0.00"),
            "commercial_discount_amount": Decimal("0.00"),
            "currency": CurrencyChoices.VES,
            "nominal_value": Decimal("0.01"),
            "exchange_rate": Decimal("1.0000"),
            "bank_transfer_amount": Decimal("0.00"),
            "mobile_payment_amount": Decimal("0.00"),
            "cash_amount": Decimal("0.00"),
            "card_pos_amount": Decimal("0.00"),
            "customer_credit_balance_amount": Decimal("0.00"),
            "refunded_amount": Decimal("0.00"),
            "fiscal_period": nc.fiscal_period,
        }
        defaults.update(kwargs)
        settlement = CreditNoteSettlement(**defaults)
        settlement.full_clean()
        settlement.save()
        return settlement

    return _create_settlement


@pytest.fixture
def credit_note_settlement(credit_note_settlement_factory) -> CreditNoteSettlement:
    """Fixture básica de liquidación de Nota de Crédito."""
    return credit_note_settlement_factory()


# ==============================================================================
# FIXTURES DE CUENTAS CONTABLES PARA PRUEBAS DE TOTALIZACIÓN
# ==============================================================================

@pytest.fixture
def account_debe(setup_accounts):
    """Cuenta genérica de saldo deudor (Caja Moneda Nacional)[cite: 6]."""
    return setup_accounts["cash_national_account"]

@pytest.fixture
def account_haber(setup_accounts):
    """Cuenta genérica de saldo acreedor (Ventas Gravadas)[cite: 6]."""
    return setup_accounts["taxable_goods_sales_account"]

@pytest.fixture
def account_debe_1(setup_accounts):
    """Cuenta deudora 1 para asientos compuestos (Banco Nacional)[cite: 6]."""
    return setup_accounts["bank_national_account"]

@pytest.fixture
def account_debe_2(setup_accounts):
    """Cuenta deudora 2 para asientos compuestos (Cuentas por Cobrar Comerciales)[cite: 6]."""
    return setup_accounts["ar_commercial_national_account"]

@pytest.fixture
def account_debe_3(setup_accounts):
    """Cuenta deudora 3 para asientos compuestos (Retenciones de IVA Acumuladas)[cite: 6]."""
    return setup_accounts["vat_withholdings_accumulated_account"]

@pytest.fixture
def account_haber_1(setup_accounts):
    """Cuenta acreedora 1 para asientos compuestos (Ventas Gravadas)[cite: 6]."""
    return setup_accounts["taxable_goods_sales_account"]

@pytest.fixture
def account_haber_2(setup_accounts):
    """Cuenta acreedora 2 para asientos compuestos (Débito Fiscal IVA)[cite: 6]."""
    return setup_accounts["vat_debit_account"]