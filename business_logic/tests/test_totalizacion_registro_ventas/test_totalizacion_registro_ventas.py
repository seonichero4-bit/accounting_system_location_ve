"""
Suite de pruebas unitarias para SalesAccountingTotalizationService.

Se enfoca en la validación del método _create_journal_entry_with_transactions,
garantizando el cumplimiento de la partida doble y las reglas de negocio
bajo la especificación técnica de totalización de ventas[cite: 3, 4].
"""

import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone

# Se asume la importación del servicio desde la ruta correspondiente en el proyecto
from business_logic.services.sales_accounting_totalization_service import SalesAccountingTotalizationService


@pytest.mark.django_db
class TestCreateJournalEntryWithTransactions:
    """Casos de prueba para la creación de asientos contables en Django-Ledger."""

    def test_id_hp_001_create_journal_entry_balanced_simple(
        self, fiscal_profile, account_debe, account_haber, ledger_model
    ) -> None:
        """[ID_HP_001] - Creación exitosa de asiento contable balanceado simple[cite: 4]."""
        # Arrange
        service = SalesAccountingTotalizationService(fiscal_profile, "2026-03")
        description = "P/R Registro Contable Simple"
        debit_entries = [(account_debe, Decimal("1000.00"), "Detalle Cargo")]
        credit_entries = [(account_haber, Decimal("1000.00"), "Detalle Abono")]
        

        # Act
        journal_entry = service._create_journal_entry_with_transactions(
            description=description,
            debit_entries=debit_entries,
            credit_entries=credit_entries,
        )

        # Assert
        assert journal_entry is not None
        assert journal_entry.transactionmodel_set.count() == 2
       #assert journal_entry.is_valid is True

    def test_id_hp_002_create_journal_entry_balanced_compound(
        self,
        fiscal_profile,
        account_debe_1,
        account_debe_2,
        account_debe_3,
        account_haber_1,
        account_haber_2,
    ) -> None:
        """[ID_HP_002] - Creación exitosa de asiento contable balanceado compuesto[cite: 4]."""
        # Arrange
        service = SalesAccountingTotalizationService(fiscal_profile, "2026-03")
        description = "Resumen General de Ventas del Período"
        debit_entries = [
            (account_debe_1, Decimal("3000.00"), "Tesorería Nacional"),
            (account_debe_2, Decimal("4000.00"), "Cuentas por Cobrar"),
            (account_debe_3, Decimal("1000.00"), "Retenciones"),
        ]
        credit_entries = [
            (account_haber_1, Decimal("5000.00"), "Ventas Gravadas"),
            (account_haber_2, Decimal("3000.00"), "Débito Fiscal"),
        ]

        # Act
        journal_entry = service._create_journal_entry_with_transactions(
            description=description,
            debit_entries=debit_entries,
            credit_entries=credit_entries,
        )

        # Assert
        assert journal_entry is not None
        assert journal_entry.transactionmodel_set.count() == 5
        #assert journal_entry.is_valid is True

    def test_id_hp_003_metadata_assignment(
        self, fiscal_profile, account_debe, account_haber
    ) -> None:
        """[ID_HP_003] - Asignación correcta de metadatos y relaciones en el Libro Diario[cite: 4]."""
        # Arrange
        service = SalesAccountingTotalizationService(fiscal_profile, "2026-03")
        description = "P/R Asiento con Metadatos"
        debit_entries = [(account_debe, Decimal("150.00"), "Cargo")]
        credit_entries = [(account_haber, Decimal("150.00"), "Abono")]

        # Act
        journal_entry = service._create_journal_entry_with_transactions(
            description=description,
            debit_entries=debit_entries,
            credit_entries=credit_entries,
        )

        # Assert
        assert journal_entry.ledger == fiscal_profile.ledger
        assert journal_entry.activity == "op"
        assert journal_entry.timestamp.date() == timezone.now().date()
        assert journal_entry.description == description

    def test_id_ec_001_unbalanced_entry_raises_validation_error(
        self, fiscal_profile, account_debe, account_haber
    ) -> None:
        """[ID_EC_001] - Rechazo por descuadre en la partida doble[cite: 4]."""
        # Arrange
        service = SalesAccountingTotalizationService(fiscal_profile, "2026-03")
        description = "Resumen General de Ventas del Período"
        debit_entries = [(account_debe, Decimal("1000.00"), "Cargo mayor")]
        credit_entries = [(account_haber, Decimal("900.00"), "Abono menor")]
        expected_msg = f"Error de cuadratura en {description} (Partida Doble)."

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            service._create_journal_entry_with_transactions(
                description=description,
                debit_entries=debit_entries,
                credit_entries=credit_entries,
            )
        assert expected_msg in str(exc_info.value)

    def test_id_ec_002_empty_entries_does_not_process(self, fiscal_profile) -> None:
        """[ID_EC_002] - Estructura de entradas vacía en el DEBE o en el HABER[cite: 4]."""
        # Arrange
        service = SalesAccountingTotalizationService(fiscal_profile, "2026-03")
        description = "Asiento Incompleto"
        debit_entries = []
        credit_entries = []

        # Act
        result = service._create_journal_entry_with_transactions(
            description=description,
            debit_entries=debit_entries,
            credit_entries=credit_entries,
        )

        # Assert
        assert result is None

    def test_id_ec_003_zero_amount_raises_validation_error(
        self, fiscal_profile, account_debe, account_haber
    ) -> None:
        """[ID_EC_003] - Inclusión de transacciones con monto igual a cero[cite: 4]."""
        # Arrange
        service = SalesAccountingTotalizationService(fiscal_profile, "2026-03")
        description = "Registro con Saldo Cero"
        debit_entries = [(account_debe, Decimal("0.00"), "Cargo nulo")]
        credit_entries = [(account_haber, Decimal("0.00"), "Abono nulo")]
        expected_msg = f"Error de validación contable en {description}: Las transacciones deben registrar montos superiores a 0.00 VES."

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            service._create_journal_entry_with_transactions(
                description=description,
                debit_entries=debit_entries,
                credit_entries=credit_entries,
            )
        assert expected_msg in str(exc_info.value)

    def test_id_ec_004_negative_amount_raises_validation_error(
        self, fiscal_profile, account_debe, account_haber
    ) -> None:
        """[ID_EC_004] - Manejo de montos negativos en las entradas del asiento[cite: 4]."""
        # Arrange
        service = SalesAccountingTotalizationService(fiscal_profile, "2026-03")
        description = "Ajuste Negativo Inválido"
        debit_entries = [(account_debe, Decimal("-500.00"), "Cargo negativo")]
        credit_entries = [(account_haber, Decimal("-500.00"), "Abono negativo")]
        expected_msg = f"Error de validación contable en {description}: No se permiten montos negativos en las transacciones del asiento contable."

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            service._create_journal_entry_with_transactions(
                description=description,
                debit_entries=debit_entries,
                credit_entries=credit_entries,
            )
        assert expected_msg in str(exc_info.value)

    def test_id_ec_005_empty_description_raises_validation_error(
        self, fiscal_profile, account_debe, account_haber
    ) -> None:
        """[ID_EC_005] - Cadena de descripción nula (None) o vacía ("")[cite: 4]."""
        # Arrange
        service = SalesAccountingTotalizationService(fiscal_profile, "2026-03")
        description = ""
        debit_entries = [(account_debe, Decimal("100.00"), "Cargo")]
        credit_entries = [(account_haber, Decimal("100.00"), "Abono")]
        expected_msg = "Error de validación en asiento contable: La descripción o glosa del asiento es requerida y no puede estar vacía."

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            service._create_journal_entry_with_transactions(
                description=description,
                debit_entries=debit_entries,
                credit_entries=credit_entries,
            )
        assert expected_msg in str(exc_info.value)

    def test_id_ec_006_null_account_raises_validation_error(
        self, fiscal_profile, account_haber
    ) -> None:
        """[ID_EC_006] - Instancia de cuenta contable nula (None) en la tupla de entradas[cite: 4]."""
        # Arrange
        service = SalesAccountingTotalizationService(fiscal_profile, "2026-03")
        description = "Asiento sin Cuenta"
        debit_entries = [(None, Decimal("100.00"), "Detalle sin cuenta")]
        credit_entries = [(account_haber, Decimal("100.00"), "Abono")]
        expected_msg = f"Error de asignación contable en {description}: La cuenta contable especificada no es válida o se encuentra ausente."

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            service._create_journal_entry_with_transactions(
                description=description,
                debit_entries=debit_entries,
                credit_entries=credit_entries,
            )
        assert expected_msg in str(exc_info.value)

    def test_id_ec_007_invalid_data_type_raises_validation_error(
        self, fiscal_profile, account_debe, account_haber
    ) -> None:
        """[ID_EC_007] - Incompatibilidad de tipos de datos en los montos de transacción[cite: 4]."""
        # Arrange
        service = SalesAccountingTotalizationService(fiscal_profile, "2026-03")
        description = "Error Tipo de Dato"
        debit_entries = [(account_debe, "100.00", "Detalle con cadena")]
        credit_entries = [(account_haber, "100.00", "Abono con cadena")]
        expected_msg = f"Error de tipo de dato en {description}: El monto de la transacción debe ser de tipo Decimal preciso."

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            service._create_journal_entry_with_transactions(
                description=description,
                debit_entries=debit_entries,
                credit_entries=credit_entries,
            )
        assert expected_msg in str(exc_info.value)

    def test_id_ec_008_malformed_tuple_raises_validation_error(
        self, fiscal_profile, account_debe, account_haber
    ) -> None:
        """[ID_EC_008] - Tupla de entrada con estructura mal formada o incompleta[cite: 4]."""
        # Arrange
        service = SalesAccountingTotalizationService(fiscal_profile, "2026-03")
        description = "Estructura Incompleta"
        debit_entries = [(account_debe, Decimal("100.00"))]  # Falta el detalle (str)
        credit_entries = [(account_haber, Decimal("100.00"), "Abono")]
        expected_msg = f"Error de formato en entradas de {description}: Cada transacción debe ser una tupla válida de (AccountModel, Decimal, str)."

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            service._create_journal_entry_with_transactions(
                description=description,
                debit_entries=debit_entries,
                credit_entries=credit_entries,
            )
        assert expected_msg in str(exc_info.value)

    def test_id_ec_009_verify_fails_raises_validation_error(
        self, fiscal_profile, account_debe, account_haber
    ) -> None:
        """[ID_EC_009] - Fallo simulado en la verificación del motor contable interno[cite: 4]."""
        # Arrange
        service = SalesAccountingTotalizationService(fiscal_profile, "2026-03")
        description = "Validación de Asiento Asíncrono"
        
        # Al no usar mocks, forzamos un escenario donde la sumatoria exacta 
        # falle a nivel de base de datos dentro de Django-Ledger, por ejemplo 
        # enviando un descuadre milimétrico que pase filtros básicos pero falle en .verify()
        debit_entries = [(account_debe, Decimal("100.00"), "Cargo base")]
        credit_entries = [(account_haber, Decimal("100.01"), "Abono con diferencia de céntimo")]
        expected_msg = f"Error de cuadratura en {description} (Partida Doble)."

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            service._create_journal_entry_with_transactions(
                description=description,
                debit_entries=debit_entries,
                credit_entries=credit_entries,
            )
        assert expected_msg in str(exc_info.value)