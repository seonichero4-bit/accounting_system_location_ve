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
        return [], [], [], []

    def _process_credit_notes(
        self, credit_notes_records: list[SalesRecord]
    ) -> tuple[
        list[tuple[AccountModel, Decimal, str]],
        list[tuple[AccountModel, Decimal, str]],
        list[tuple[AccountModel, Decimal, str]],
        list[tuple[AccountModel, Decimal, str]],
    ]:
        """Procesa y consolida las notas de crédito del período actual."""
        return [], [], [], []

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