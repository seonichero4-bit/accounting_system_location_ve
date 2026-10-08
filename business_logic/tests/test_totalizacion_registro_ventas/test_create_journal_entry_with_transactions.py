"""Módulo de pruebas unitarias para _create_journal_entry_with_transactions.

Contiene la suite automatizada completa correspondiente al plan de pruebas unitarias
para el método de creación y verificación de asientos contables del servicio
SalesAccountingTotalizationService.
"""

from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django_ledger.models import JournalEntryModel, TransactionModel

from business_logic.services.sales_accounting_totalization_service import (
    SalesAccountingTotalizationService,
)


@pytest.mark.django_db
class TestCreateJournalEntryWithTransactions:
    """Suite de pruebas unitarias para el método _create_journal_entry_with_transactions."""

    def test_ID_HP_001_create_and_verify_balanced_journal_entry_success(
        self,
        fiscal_profile,
        account_debe,
        account_debe_1,
        account_haber,
    ) -> None:
        """Validar la creación exitosa y verificación de un asiento contable balanceado."""
        # --- Arrange ---
        service = SalesAccountingTotalizationService(
            fiscal_profile=fiscal_profile,
            fiscal_period="2026-01",
        )
        description = "P/R Registro del resumen de ventas de bienes del período fiscal"
        debit_entries = [
            (account_debe, Decimal("100.00"), "Cobro en efectivo"),
            (account_debe_1, Decimal("50.00"), "Cobro por transferencia"),
        ]
        credit_entries = [
            (account_haber, Decimal("150.00"), "Ingreso por ventas de bienes"),
        ]

        # --- Act ---
        journal_entry = service._create_journal_entry_with_transactions(
            description=description,
            debit_entries=debit_entries,
            credit_entries=credit_entries,
        )

        # --- Assert ---
        assert isinstance(journal_entry, JournalEntryModel)
        assert journal_entry.ledger == fiscal_profile.ledger
        assert journal_entry.activity == "op"
        assert journal_entry.description == description
        assert journal_entry.timestamp is not None

        debit_txs = TransactionModel.objects.filter(
            journal_entry=journal_entry, tx_type="debit"
        )
        credit_txs = TransactionModel.objects.filter(
            journal_entry=journal_entry, tx_type="credit"
        )

        assert debit_txs.count() == 2
        assert credit_txs.count() == 1

        debit_tx_1 = debit_txs.get(account=account_debe)
        assert debit_tx_1.amount == Decimal("100.00")
        assert debit_tx_1.description == "Cobro en efectivo"

        debit_tx_2 = debit_txs.get(account=account_debe_1)
        assert debit_tx_2.amount == Decimal("50.00")
        assert debit_tx_2.description == "Cobro por transferencia"

        credit_tx_1 = credit_txs.get(account=account_haber)
        assert credit_tx_1.amount == Decimal("150.00")
        assert credit_tx_1.description == "Ingreso por ventas de bienes"

        assert journal_entry.verify()[1] is True

    def test_ID_HP_002_apply_decimal_precision_and_explicit_rounding(
        self,
        fiscal_profile,
        account_debe,
        account_debe_1,
        account_haber,
    ) -> None:
        """Validar redondeo explícito a dos posiciones decimales en la cuantificación de entradas."""
        # --- Arrange ---
        service = SalesAccountingTotalizationService(
            fiscal_profile=fiscal_profile,
            fiscal_period="2026-01",
        )
        description = "Asiento con montos acumulados con más de dos decimales"
        debit_entries = [
            (account_debe, Decimal("100.556"), "Ingreso caja"),
            (account_debe_1, Decimal("49.444"), "Ingreso banco"),
        ]
        credit_entries = [
            (account_haber, Decimal("150.000"), "Ingreso ventas"),
        ]

        # --- Act ---
        journal_entry = service._create_journal_entry_with_transactions(
            description=description,
            debit_entries=debit_entries,
            credit_entries=credit_entries,
        )

        # --- Assert ---
        assert journal_entry is not None
        debit_tx_1 = TransactionModel.objects.get(
            journal_entry=journal_entry, account=account_debe
        )
        debit_tx_2 = TransactionModel.objects.get(
            journal_entry=journal_entry, account=account_debe_1
        )
        credit_tx = TransactionModel.objects.get(
            journal_entry=journal_entry, account=account_haber
        )

        assert debit_tx_1.amount == Decimal("100.56")
        assert debit_tx_2.amount == Decimal("49.44")
        assert credit_tx.amount == Decimal("150.00")

        total_debit = debit_tx_1.amount + debit_tx_2.amount
        total_credit = credit_tx.amount
        assert total_debit == total_credit
        assert journal_entry.verify()[1] is True

    def test_ID_HP_003_create_balanced_entry_with_asymmetric_structure(
        self,
        fiscal_profile,
        account_debe,
        account_debe_1,
        account_debe_3,
        account_haber_1,
        account_haber_2,
    ) -> None:
        """Validar registro de transacción compuesta con estructura asimétrica N débitos a M créditos."""
        # --- Arrange ---
        service = SalesAccountingTotalizationService(
            fiscal_profile=fiscal_profile,
            fiscal_period="2026-01",
        )
        description = "Resumen de ventas con múltiples retenciones e impuestos"
        debit_entries = [
            (account_debe_1, Decimal("42.00"), "Cobro"),
            (account_debe, Decimal("42.00"), "Cobro"),
            (account_debe_3, Decimal("16.00"), "Retención IVA"),
        ]
        credit_entries = [
            (account_haber_1, Decimal("86.21"), "Venta"),
            (account_haber_2, Decimal("13.79"), "IVA 16%"),
        ]

        # --- Act ---
        journal_entry = service._create_journal_entry_with_transactions(
            description=description,
            debit_entries=debit_entries,
            credit_entries=credit_entries,
        )

        # --- Assert ---
        debit_count = TransactionModel.objects.filter(
            journal_entry=journal_entry, tx_type="debit"
        ).count()
        credit_count = TransactionModel.objects.filter(
            journal_entry=journal_entry, tx_type="credit"
        ).count()

        assert debit_count == 3
        assert credit_count == 2
        assert journal_entry.verify()[1] is True

    def test_ID_EC_001_unbalanced_entry_raises_validation_error(
        self,
        fiscal_profile,
        account_debe,
        account_haber,
    ) -> None:
        """Validar que un descuadre intencional en la partida doble lance ValidationError."""
        # --- Arrange ---
        service = SalesAccountingTotalizationService(
            fiscal_profile=fiscal_profile,
            fiscal_period="2026-01",
        )
        description = "Asiento descuadrado intencional"
        debit_entries = [
            (account_debe, Decimal("100.00"), "Cobro"),
        ]
        credit_entries = [
            (account_haber, Decimal("90.00"), "Venta"),
        ]

        # --- Act & Assert ---
        with pytest.raises(ValidationError):
            service._create_journal_entry_with_transactions(
                description=description,
                debit_entries=debit_entries,
                credit_entries=credit_entries,
            )

    def test_ID_EC_002_unbalanced_entry_from_independent_quantization_raises_validation_error(
        self,
        fiscal_profile,
        account_debe,
        account_debe_1,
        account_haber,
    ) -> None:
        """Validar que la diferencia de centavos por cuantificación decimal independiente lance ValidationError."""
        # --- Arrange ---
        service = SalesAccountingTotalizationService(
            fiscal_profile=fiscal_profile,
            fiscal_period="2026-01",
        )
        description = "Asiento descuadrado por redondeo individual"
        debit_entries = [
            (account_debe, Decimal("10.004"), "Partida 1"),
            (account_debe_1, Decimal("10.004"), "Partida 2"),
        ]
        credit_entries = [
            (account_haber, Decimal("20.008"), "Venta"),
        ]

        # --- Act & Assert ---
        with pytest.raises(ValidationError):
            service._create_journal_entry_with_transactions(
                description=description,
                debit_entries=debit_entries,
                credit_entries=credit_entries,
            )

    def test_ID_EC_003_empty_transaction_lists_returns_none_without_persistence(
        self,
        fiscal_profile,
    ) -> None:
        """Validar que recibir listas vacías de transacciones aborte el proceso retornando None sin persistir datos."""
        # --- Arrange ---
        service = SalesAccountingTotalizationService(
            fiscal_profile=fiscal_profile,
            fiscal_period="2026-01",
        )
        description = "P/R Asiento sin movimientos de débito o crédito"
        debit_entries = []
        credit_entries = []

        initial_entries_count = JournalEntryModel.objects.filter(
            description=description
        ).count()
        initial_tx_count = TransactionModel.objects.count()

        # --- Act ---
        result = service._create_journal_entry_with_transactions(
            description=description,
            debit_entries=debit_entries,
            credit_entries=credit_entries,
        )

        # --- Assert ---
        assert result is None
        assert (
            JournalEntryModel.objects.filter(description=description).count()
            == initial_entries_count
        )
        assert TransactionModel.objects.count() == initial_tx_count

    def test_ID_EC_004_negative_amounts_in_entries_raises_validation_error(
        self,
        fiscal_profile,
        account_debe,
        account_haber,
    ) -> None:
        """Validar que la presencia de montos negativos en las entradas lance ValidationError."""
        # --- Arrange ---
        service = SalesAccountingTotalizationService(
            fiscal_profile=fiscal_profile,
            fiscal_period="2026-01",
        )
        description = "Asiento con montos negativos"
        debit_entries = [
            (account_debe, Decimal("-100.00"), "Monto negativo invalido"),
        ]
        credit_entries = [
            (account_haber, Decimal("-100.00"), "Monto negativo invalido"),
        ]

        # --- Act & Assert ---
        with pytest.raises(ValidationError):
            service._create_journal_entry_with_transactions(
                description=description,
                debit_entries=debit_entries,
                credit_entries=credit_entries,
            )

    def test_ID_EC_005_zero_amount_transaction_in_balanced_entry_raises_validation_error(
        self,
        fiscal_profile,
        account_debe,
        account_debe_1,
        account_haber,
    ) -> None:
        """Validar que incluir una partida de valor 0.00 en un asiento balanceado lance ValidationError al auditar con verify()."""
        # --- Arrange ---
        service = SalesAccountingTotalizationService(
            fiscal_profile=fiscal_profile,
            fiscal_period="2026-01",
        )
        description = "Asiento balanceado con partida nula de monto cero"
        debit_entries = [
            (account_debe, Decimal("200.00"), "Cobro efectivo"),
            (account_debe_1, Decimal("0.00"), "Transacción en cero"),
        ]
        credit_entries = [
            (account_haber, Decimal("200.00"), "Ingreso por ventas"),
        ]

        # --- Act & Assert ---
        with pytest.raises(ValidationError):
            service._create_journal_entry_with_transactions(
                description=description,
                debit_entries=debit_entries,
                credit_entries=credit_entries,
            )