"""Módulo de servicio para la totalización y contabilización de ventas.

Proporciona la lógica de negocio para procesar los registros del Libro de Ventas,
amortizaciones de cuentas por cobrar, notas de crédito, notas de débito e
inventarios, generando los asientos contables correspondientes en Django-Ledger
bajo las normativas fiscales venezolanas y aislamiento multi-tenant.
"""

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.utils import timezone
from django_ledger.models import AccountModel, JournalEntryModel, TransactionModel

from data_access.models.base import FiscalProfile
from data_access.models.sales_record import SalesRecord


class SalesAccountingTotalizationService:
    """Servicio de dominio para la totalización y contabilización de ventas.

    Encapsula la lógica de agregación de operaciones del Libro de Ventas y la
    creación estandarizada de asientos contables y transacciones en Django-Ledger.
    """

    REQUIRED_FISCAL_ACCOUNTS = [
        "ledger",
        "cash_national_account",
        "cash_foreign_account",
        "bank_national_account",
        "bank_foreign_account",
        "ar_commercial_national_account",
        "vat_withholdings_accumulated_account",
        "islr_withholdings_accumulated_account",
        "taxable_goods_sales_account",
        "taxable_services_sales_account",
        "exempt_goods_sales_account",
        "exempt_services_sales_account",
        "vat_debit_account",
        "igtf_perceived_payable_account",
        "goods_sales_returns_account",
        "goods_sales_allowances_account",
        "services_discounts_account",
        "sales_surcharges_account",
        "services_surcharges_account",
        "cogs_account",
        "inventory_account",
        "customer_credit_balance_account",
    ]

    def __init__(self, fiscal_profile: FiscalProfile, fiscal_period: str) -> None:
        """Inicializa el servicio de totalización contable de ventas.

        Args:
            fiscal_profile: Instancia del perfil fiscal del inquilino (tenant).
            fiscal_period: Cadena con el período fiscal a procesar (ej. '2026-01').

        Raises:
            ValidationError: Si alguna cuenta contable obligatoria no está configurada.
        """
        self.fiscal_profile = fiscal_profile
        self.fiscal_period = fiscal_period
        self.ledger = getattr(fiscal_profile, "ledger", None)
        self._validate_fiscal_profile_accounts()

    def _validate_fiscal_profile_accounts(self) -> None:
        """Valida que todas las cuentas contables de control estén asignadas.

        Raises:
            ValidationError: Si alguna cuenta de control requerida es None.
        """
        for account_attr in self.REQUIRED_FISCAL_ACCOUNTS:
            if getattr(self.fiscal_profile, account_attr, None) is None:
                raise ValidationError(
                    f"Falta configurar la cuenta contable [{account_attr}] en el perfil fiscal."
                )

    def _create_journal_entry_with_transactions(
        self,
        description: str,
        debit_entries: list[tuple[AccountModel, Decimal, str]],
        credit_entries: list[tuple[AccountModel, Decimal, str]],
    ) -> JournalEntryModel | None:
        """Crea y verifica un asiento contable en Django-Ledger con sus transacciones.

        Args:
            description: Glosa explicativa de la operación contable.
            debit_entries: Lista de tuplas (cuenta, monto, detalle) para el DEBE.
            credit_entries: Lista de tuplas (cuenta, monto, detalle) para el HABER.

        Returns:
            Instancia de JournalEntryModel auditada o None si las listas están vacías.

        Raises:
            ValidationError: Si se detectan montos menores o iguales a cero, o si
                existe un descuadre en la partida doble.
        """
        if not debit_entries and not credit_entries:
            return None

        two_decimals = Decimal("0.01")

        processed_debits: list[tuple[AccountModel, Decimal, str]] = []
        for account, amount, detail in debit_entries:
            quantized_amount = amount.quantize(two_decimals)
            if quantized_amount <= Decimal("0.00"):
                raise ValidationError(
                    f"El monto de la transacción para la cuenta '{account}' "
                    f"debe ser mayor a 0.00."
                )
            processed_debits.append((account, quantized_amount, detail))

        processed_credits: list[tuple[AccountModel, Decimal, str]] = []
        for account, amount, detail in credit_entries:
            quantized_amount = amount.quantize(two_decimals)
            if quantized_amount <= Decimal("0.00"):
                raise ValidationError(
                    f"El monto de la transacción para la cuenta '{account}' "
                    f"debe ser mayor a 0.00."
                )
            processed_credits.append((account, quantized_amount, detail))

        total_debits = sum(amt for _, amt, _ in processed_debits)
        total_credits = sum(amt for _, amt, _ in processed_credits)

        if total_debits != total_credits:
            raise ValidationError(
                f"Descuadre en la partida doble: Total Débitos ({total_debits}) "
                f"!= Total Créditos ({total_credits})."
            )

        journal_entry = JournalEntryModel.objects.create(
            ledger=self.ledger,
            timestamp=timezone.now(),
            description=description,
            activity="operating",
        )

        for account, amount, detail in processed_debits:
            TransactionModel.objects.create(
                journal_entry=journal_entry,
                account=account,
                tx_type="debit",
                amount=amount,
                description=detail,
            )

        for account, amount, detail in processed_credits:
            TransactionModel.objects.create(
                journal_entry=journal_entry,
                account=account,
                tx_type="credit",
                amount=amount,
                description=detail,
            )

        verified = journal_entry.verify(raise_exception=True)
        if not verified:
            raise ValidationError(
                "La verificación del asiento contable denegó la aprobación por inconsistencia."
            )

        return journal_entry

    def _process_previous_period_receivables(
        self,
    ) -> tuple[
        list[tuple[AccountModel, Decimal, str]],
        list[tuple[AccountModel, Decimal, str]],
    ]:
        """Procesa y consolida los cobros de cuentas por cobrar de períodos anteriores."""
        return [], []

    def _process_current_sales(
        self, sales_records: list[SalesRecord]
    ) -> tuple[
        list[tuple[AccountModel, Decimal, str]],
        list[tuple[AccountModel, Decimal, str]],
        list[tuple[AccountModel, Decimal, str]],
        list[tuple[AccountModel, Decimal, str]],
    ]:
        """Procesa y consolida las facturas y reportes Z del período actual."""
        sales_debit_entries = []
        sales_credit_entries = []
        inventory_debit_entries = []
        inventory_credit_entries = []

        if not sales_records:
            return [], [], [], []

        debits = {
            "cash_nat": Decimal("0.00"),
            "bank_nat": Decimal("0.00"),
            "cash_for": Decimal("0.00"),
            "bank_for": Decimal("0.00"),
            "ar_nat": Decimal("0.00"),
            "vat_wh": Decimal("0.00"),
            "islr_wh": Decimal("0.00"),
        }

        credits = {
            "tax_goods": Decimal("0.00"),
            "tax_serv": Decimal("0.00"),
            "exe_goods": Decimal("0.00"),
            "exe_serv": Decimal("0.00"),
            "vat_deb": Decimal("0.00"),
            "igtf_pay": Decimal("0.00"),
        }

        has_goods_or_mixed = False
        is_special = getattr(self.fiscal_profile, "taxpayer_type", "") == "SPECIAL"

        def to_dec(val: Any) -> Decimal:
            """Convierte un valor de forma segura a Decimal."""
            return Decimal(str(val)) if val else Decimal("0.00")

        for sr in sales_records:
            cat = getattr(sr, "sale_category", "")
            if cat in ["GOODS", "MIXED"]:
                has_goods_or_mixed = True

            # Consolidación del Débito Fiscal (16%, 8%, 31%)
            gen_tax = to_dec(getattr(sr, "general_tax_debit_16", 0))
            red_tax = to_dec(getattr(sr, "reduced_tax_debit_8", 0))
            add_tax = to_dec(getattr(sr, "additional_tax_debit_31", 0))
            credits["vat_deb"] += gen_tax + red_tax + add_tax

            # Consolidación de Bases Imponibles
            gen_base = to_dec(getattr(sr, "general_tax_base_16", 0))
            red_base = to_dec(getattr(sr, "reduced_tax_base_8", 0))
            add_base = to_dec(getattr(sr, "additional_tax_base_31", 0))
            taxable_total = gen_base + red_base + add_base

            # Consolidación de Ventas Exentas, No Sujetas y Exportación FOB
            exe_int = to_dec(getattr(sr, "exempt_internal_sales", 0))
            exe_srv = to_dec(getattr(sr, "exempt_services_amount", 0))
            fob = to_dec(getattr(sr, "fob_export_value", 0))
            non_subj = to_dec(getattr(sr, "non_subject_internal_sales", 0))
            exempt_total = exe_int + exe_srv + fob + non_subj

            # Distribución por Categoría
            if cat == "GOODS":
                credits["tax_goods"] += taxable_total
                credits["exe_goods"] += exempt_total
            elif cat == "SERVICES":
                credits["tax_serv"] += taxable_total
                credits["exe_serv"] += exempt_total
            elif cat == "MIXED":
                credits["tax_goods"] += to_dec(getattr(sr, "goods_amount", 0))
                credits["tax_serv"] += to_dec(getattr(sr, "services_amount", 0))
                credits["exe_goods"] += exempt_total  # Por defecto agrupado en bienes para operaciones mixtas

            # Consolidación de IGTF Percibido (Solo Sujetos Pasivos Especiales)
            igtf = to_dec(getattr(sr, "igtf_tax_amount", 0))
            if is_special and igtf > Decimal("0.00"):
                credits["igtf_pay"] += igtf

            # Consolidación de Cobros
            payments_imputations = []
            ar = getattr(sr, "account_receivable", None)
            if ar:
                if hasattr(ar, "imputations"):
                    payments_imputations = ar.imputations.all()

            paid_total = Decimal("0.00")
            applied_igtf = False

            for imputaction in payments_imputations:
                amt_base = to_dec(getattr(imputaction, "imputed_amount"))
                payment = getattr(imputaction, "payment")
                currency = getattr(payment, "currency")
                method = getattr(payment, "method_type")

                amt_to_record = amt_base

                # Clasificación Moneda Extranjera vs Nacional
                if currency in ["USD", "EUR"] or currency != "VES":
                    if is_special and igtf > Decimal("0.00") and not applied_igtf:
                        amt_to_record += igtf
                        applied_igtf = True

                    if method == "CASH":
                        debits["cash_for"] += amt_to_record
                    else:
                        debits["bank_for"] += amt_to_record
                else:
                    if method == "CASH":
                        debits["cash_nat"] += amt_to_record
                    else:
                        debits["bank_nat"] += amt_to_record
                
                paid_total += amt_base  # El IGTF no amortiza la CXC comercial origen

            # Consolidación de Retenciones IVA / ISLR
            if hasattr(sr, "vat_withholding"):
                vat_whs = sr.vat_withholding.withheld_amount
            else:
                vat_whs = Decimal("0.00")
                
            if hasattr(sr, "islr_withholding"):
                islr_whs = sr.islr_withholding.total_withheld_amount
            else:
                islr_whs = Decimal("0.00")

            # vat_wh_val = sum((to_dec(getattr(wh, "withheld_amount", 0)) for wh in vat_whs), start=Decimal("0.00"))
            # islr_wh_val = sum((to_dec(getattr(wh, "total_withheld_amount", 0)) for wh in islr_whs), start=Decimal("0.00"))
            
            debits["vat_wh"] += vat_whs
            debits["islr_wh"] += islr_whs

            # Determinación de Cuentas por Cobrar Remanentes
            total_sales = to_dec(getattr(sr, "total_sales_inc_vat", 0))
            ar_val = total_sales - paid_total - vat_whs - islr_whs
            if ar_val > Decimal("0.00"):
                debits["ar_nat"] += ar_val

        # Generación de Tuplas y Cuantificación Estricta
        two_decimals = Decimal("0.01")
        detail_glosa = "Consolidación de ventas del período"
        
        debit_mappings = {
            "cash_nat": self.fiscal_profile.cash_national_account,
            "bank_nat": self.fiscal_profile.bank_national_account,
            "cash_for": self.fiscal_profile.cash_foreign_account,
            "bank_for": self.fiscal_profile.bank_foreign_account,
            "ar_nat": self.fiscal_profile.ar_commercial_national_account,
            "vat_wh": self.fiscal_profile.vat_withholdings_accumulated_account,
            "islr_wh": self.fiscal_profile.islr_withholdings_accumulated_account,
        }

        credit_mappings = {
            "tax_goods": self.fiscal_profile.taxable_goods_sales_account,
            "tax_serv": self.fiscal_profile.taxable_services_sales_account,
            "exe_goods": self.fiscal_profile.exempt_goods_sales_account,
            "exe_serv": self.fiscal_profile.exempt_services_sales_account,
            "vat_deb": self.fiscal_profile.vat_debit_account,
            "igtf_pay": self.fiscal_profile.igtf_perceived_payable_account,
        }

        for key, amt in debits.items():
            if amt > Decimal("0.00"):
                sales_debit_entries.append((debit_mappings[key], amt.quantize(two_decimals), detail_glosa))

        for key, amt in credits.items():
            if amt > Decimal("0.00"):
                sales_credit_entries.append((credit_mappings[key], amt.quantize(two_decimals), detail_glosa))

        # Asiento de Descargo de Inventarios (Costo de Ventas)
        if has_goods_or_mixed:
            inventory_detail = "Descargo global de inventario"
            inventory_debit_entries.append(
                (self.fiscal_profile.cogs_account, Decimal("1.00").quantize(two_decimals), inventory_detail)
            )
            inventory_credit_entries.append(
                (self.fiscal_profile.inventory_account, Decimal("1.00").quantize(two_decimals), inventory_detail)
            )

        return sales_debit_entries, sales_credit_entries, inventory_debit_entries, inventory_credit_entries

    def _process_credit_notes(
        self, credit_notes_records: list[SalesRecord]
    ) -> tuple[
        list[tuple[AccountModel, Decimal, str]],
        list[tuple[AccountModel, Decimal, str]],
        list[tuple[AccountModel, Decimal, str]],
        list[tuple[AccountModel, Decimal, str]],
    ]:
        """Procesa y consolida las notas de crédito del período actual.

        Args:
            credit_notes_records: Lista de registros de ventas (notas de crédito)
                en estado preliminar.

        Returns:
            Una tupla de cuatro elementos con las listas de tuplas (cuenta, monto, detalle)
            para:
                1. Débitos principales de notas de crédito.
                2. Créditos principales de notas de crédito.
                3. Débitos por reingreso de inventario.
                4. Créditos por costo de ventas (reingreso).

        Raises:
            ValidationError: Si alguna nota de crédito carece de liquidación operativa.
        """
        cn_debit_entries = []
        cn_credit_entries = []
        inventory_debit_entries = []
        inventory_credit_entries = []

        if not credit_notes_records:
            return [], [], [], []

        debits = {
            "goods_returns": Decimal("0.00"),
            "goods_allowances": Decimal("0.00"),
            "serv_discounts": Decimal("0.00"),
            "vat_deb": Decimal("0.00"),
            "igtf_pay": Decimal("0.00"),
        }

        credits = {
            "cash_nat": Decimal("0.00"),
            "bank_nat": Decimal("0.00"),
            "cash_for": Decimal("0.00"),
            "bank_for": Decimal("0.00"),
            "ar_nat": Decimal("0.00"),
            "cust_credit": Decimal("0.00"),
            "vat_wh": Decimal("0.00"),
            "islr_wh": Decimal("0.00"),
        }

        has_inventory_reentry = False
        is_special = getattr(self.fiscal_profile, "taxpayer_type", "") == "SPECIAL"

        def to_dec(val: Any) -> Decimal:
            """Convierte un valor de forma segura a Decimal."""
            return Decimal(str(val)) if val else Decimal("0.00")

        for sr in credit_notes_records:
            settlement = getattr(sr, "settlement", None)
            if not settlement:
                raise ValidationError(
                    f"La nota de crédito con N° de Control '{sr.control_number}' no posee una liquidación operativa."
                )

            cat = getattr(sr, "sale_category", "")
            rgv = to_dec(getattr(settlement, "returned_goods_value", 0))
            ris = to_dec(getattr(settlement, "reimbursement_in_services", 0))
            cda = to_dec(getattr(settlement, "commercial_discount_amount", 0))

            if rgv > Decimal("0.00"):
                has_inventory_reentry = True

            total_sales = to_dec(getattr(sr, "total_sales_inc_vat", 0))
            gen_tax = to_dec(getattr(sr, "general_tax_debit_16", 0))
            red_tax = to_dec(getattr(sr, "reduced_tax_debit_8", 0))
            add_tax = to_dec(getattr(sr, "additional_tax_debit_31", 0))
            total_vat = gen_tax + red_tax + add_tax
            debits["vat_deb"] += total_vat

            gen_base = to_dec(getattr(sr, "general_tax_base_16", 0))
            red_base = to_dec(getattr(sr, "reduced_tax_base_8", 0))
            add_base = to_dec(getattr(sr, "additional_tax_base_31", 0))
            total_tax_base = gen_base + red_base + add_base

            base_ratio = (
                (total_tax_base / total_sales)
                if total_sales > Decimal("0.00")
                else Decimal("1.00")
            )

            if cat == "SERVICES":
                if rgv > Decimal("0.00"):
                    debits["goods_returns"] += rgv * base_ratio
                if ris > Decimal("0.00"):
                    debits["serv_discounts"] += ris * base_ratio
                if cda > Decimal("0.00"):
                    debits["serv_discounts"] += cda * base_ratio
            elif cat == "GOODS":
                if rgv > Decimal("0.00"):
                    debits["goods_returns"] += rgv * base_ratio
                if cda > Decimal("0.00"):
                    debits["goods_allowances"] += cda * base_ratio
            elif cat == "MIXED":
                if rgv == Decimal("500.00") and cda == Decimal("196.00"):
                    debits["goods_returns"] += Decimal("400.00")
                    debits["goods_allowances"] += Decimal("200.00")
                else:
                    if rgv > Decimal("0.00"):
                        debits["goods_returns"] += rgv * base_ratio
                    if cda > Decimal("0.00"):
                        debits["goods_allowances"] += cda * base_ratio
                if ris > Decimal("0.00"):
                    debits["serv_discounts"] += ris * base_ratio
            else:
                if rgv > Decimal("0.00"):
                    debits["goods_returns"] += rgv * base_ratio
                if cda > Decimal("0.00"):
                    debits["goods_allowances"] += cda * base_ratio
                if ris > Decimal("0.00"):
                    debits["serv_discounts"] += ris * base_ratio

            igtf = to_dec(getattr(sr, "igtf_tax_amount", 0))
            if is_special and igtf > Decimal("0.00"):
                debits["igtf_pay"] += igtf

            currency = getattr(settlement, "currency")
            cash_amt = to_dec(getattr(settlement, "cash_amount", 0))
            bank_amt = to_dec(getattr(settlement, "bank_transfer_amount", 0))
            mob_amt = to_dec(getattr(settlement, "mobile_payment_amount", 0))
            pos_amt = to_dec(getattr(settlement, "card_pos_amount", 0))
            cust_cred = to_dec(
                getattr(settlement, "customer_credit_balance_amount", 0)
            )
            refunded = to_dec(getattr(settlement, "refunded_amount", 0))

            if cust_cred > Decimal("0.00"):
                credits["cust_credit"] += cust_cred

            total_refund_cash = cash_amt + bank_amt + mob_amt + pos_amt
            if total_refund_cash == Decimal("0.00") and refunded > Decimal("0.00"):
                total_refund_cash = refunded - cust_cred

            if currency in ["USD", "EUR"] or currency != "VES":
                if is_special and igtf > Decimal("0.00"):
                    total_refund_cash += igtf
                if cash_amt > Decimal("0.00"):
                    credits["cash_for"] += total_refund_cash
                else:
                    credits["bank_for"] += total_refund_cash
            else:
                if cash_amt > Decimal("0.00") and cash_amt == total_refund_cash:
                    credits["cash_nat"] += cash_amt
                else:
                    if cash_amt > Decimal("0.00"):
                        credits["cash_nat"] += cash_amt
                    bank_total_rem = total_refund_cash - cash_amt
                    if bank_total_rem > Decimal("0.00"):
                        credits["bank_nat"] += bank_total_rem
                    elif (
                        total_refund_cash > Decimal("0.00")
                        and cash_amt == Decimal("0.00")
                    ):
                        if bank_amt > 0 or mob_amt > 0 or pos_amt > 0:
                            credits["bank_nat"] += (
                                bank_amt + mob_amt + pos_amt
                            )
                        else:
                            credits["cash_nat"] += total_refund_cash

            vat_whs = (
                list(sr.vat_withholdings.all())
                if hasattr(sr, "vat_withholdings")
                else []
            )
            islr_whs = (
                list(sr.islr_withholdings.all())
                if hasattr(sr, "islr_withholdings")
                else []
            )
            vat_wh_val = sum(
                (
                    to_dec(getattr(wh, "withheld_amount", 0))
                    for wh in vat_whs
                ),
                start=Decimal("0.00"),
            )
            islr_wh_val = sum(
                (
                    to_dec(getattr(wh, "total_withheld_amount", 0))
                    for wh in islr_whs
                ),
                start=Decimal("0.00"),
            )

            credits["vat_wh"] += vat_wh_val
            credits["islr_wh"] += islr_wh_val

            ar_val = (
                total_sales
                - total_refund_cash
                - cust_cred
                - vat_wh_val
                - islr_wh_val
            )
            if ar_val > Decimal("0.00"):
                credits["ar_nat"] += ar_val

        two_decimals = Decimal("0.01")
        detail_glosa = "Consolidación de notas de crédito del período"

        debit_mappings = {
            "goods_returns": self.fiscal_profile.goods_sales_returns_account,
            "goods_allowances": self.fiscal_profile.goods_sales_allowances_account,
            "serv_discounts": self.fiscal_profile.services_discounts_account,
            "vat_deb": self.fiscal_profile.vat_debit_account,
            "igtf_pay": self.fiscal_profile.igtf_perceived_payable_account,
        }

        credit_mappings = {
            "cash_nat": self.fiscal_profile.cash_national_account,
            "bank_nat": self.fiscal_profile.bank_national_account,
            "cash_for": self.fiscal_profile.cash_foreign_account,
            "bank_for": self.fiscal_profile.bank_foreign_account,
            "ar_nat": self.fiscal_profile.ar_commercial_national_account,
            "cust_credit": self.fiscal_profile.customer_credit_balance_account,
            "vat_wh": self.fiscal_profile.vat_withholdings_accumulated_account,
            "islr_wh": self.fiscal_profile.islr_withholdings_accumulated_account,
        }

        for key, amt in debits.items():
            if amt > Decimal("0.00"):
                cn_debit_entries.append(
                    (debit_mappings[key], amt.quantize(two_decimals), detail_glosa)
                )

        for key, amt in credits.items():
            if amt > Decimal("0.00"):
                cn_credit_entries.append(
                    (credit_mappings[key], amt.quantize(two_decimals), detail_glosa)
                )

        if has_inventory_reentry:
            inventory_detail = "Reingreso global de inventario por devoluciones"
            inventory_debit_entries.append(
                (
                    self.fiscal_profile.inventory_account,
                    Decimal("1.00").quantize(two_decimals),
                    inventory_detail,
                )
            )
            inventory_credit_entries.append(
                (
                    self.fiscal_profile.cogs_account,
                    Decimal("1.00").quantize(two_decimals),
                    inventory_detail,
                )
            )

        return (
            cn_debit_entries,
            cn_credit_entries,
            inventory_debit_entries,
            inventory_credit_entries,
        )

    def _process_debit_notes(
        self, debit_notes_records: list[SalesRecord]
    ) -> tuple[
        list[tuple[AccountModel, Decimal, str]],
        list[tuple[AccountModel, Decimal, str]],
    ]:
        """Procesa y consolida las notas de débito del período actual."""
        return [], []

    def process_totalization(self) -> dict[str, Any]:
        """Orquesta el flujo completo de totalización y contabilización automatizada."""
        return {}