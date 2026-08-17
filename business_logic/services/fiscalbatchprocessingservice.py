from decimal import Decimal
from typing import Dict, Tuple
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from django_ledger.models import (
    JournalEntryModel,
    TransactionModel,
    AccountModel,
)

from data_access.models.base import FiscalProfile
from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.vat_withholding import VatWithholdingCertificate
from data_access.models.islr_withholding import IslrWithholdingCertificate


class FiscalBatchProcessingService:
    """Servicio de procesamiento y contabilización en lote del Libro de Compras.
    
    Integra las reglas de retención y liquidación fiscal venezolana con el ORM
    de Django Ledger, aislando las cuentas por perfil fiscal.
    """

    def __init__(
        self,
        fiscal_profile: FiscalProfile,
        fiscal_period: str,
    ):
        """Inicializa el servicio con el perfil fiscal del inquilino y el período.

        Args:
            fiscal_profile: Instancia del modelo FiscalProfile con sus FKs
                            hacia LedgerModel y AccountModel configuradas.
            fiscal_period: Período fiscal en formato MM-YYYY.
        """
        self.fiscal_profile = fiscal_profile
        self.fiscal_period = fiscal_period
        self.ledger = fiscal_profile.ledger

        # Validar la presencia de la configuración contable requerida en el perfil
        self._validate_profile_accounting_config()

    def _validate_profile_accounting_config(self) -> None:
        """Verifica que el FiscalProfile contenga todas las cuentas de control necesarias."""
        required_attrs = [
            "ledger",
            "inventory_account",
            "vat_credit_account",
            "igtf_expense_account",
            "islr_payable_account",
            "cxp_suppliers_account",
            "vat_withheld_payable_account",
        ]
        missing = [attr for attr in required_attrs if getattr(self.fiscal_profile, attr, None) is None]
        if missing:
            raise ValidationError(
                f"El perfil fiscal {self.fiscal_profile} carece de la configuración contable: {', '.join(missing)}"
            )

    @transaction.atomic
    def execute_batch_processing(self) -> Tuple[JournalEntryModel, JournalEntryModel | None, JournalEntryModel | None]:
        """Ejecuta el procesamiento atómico del lote y genera los asientos contables."""
        batch_invoices = PurchaseLedgerInvoice.objects.filter(
            fiscal_profile=self.fiscal_profile,
            fiscal_period=self.fiscal_period,
            status=PurchaseLedgerInvoice.InvoiceStatus.PRELIMINARY,
        )

        if not batch_invoices.exists():
            raise ValidationError(
                f"No existen facturas preliminares para el período {self.fiscal_period}."
            )

        # ---------------------------------------------------------------------
        # FASE 1: Acumulación de Inventario
        # ---------------------------------------------------------------------
        t_inventario = Decimal("0.00")
        t_iva_inv = Decimal("0.00")
        t_igtf_inv = Decimal("0.00")
        t_cxp_inv = Decimal("0.00")

        inventory_invoices = batch_invoices.filter(
            invoicecategory=PurchaseLedgerInvoice.InvoiceCategory.INVENTARIO
        )

        for inv in inventory_invoices:
            sign = Decimal("1.00") if inv.document_type in [
                PurchaseLedgerInvoice.DocumentType.INVOICE,
                PurchaseLedgerInvoice.DocumentType.DEBIT_NOTE,
            ] else Decimal("-1.00")

            costo_neto = sign * (
                inv.taxable_base
                + inv.exempt_amount
                + inv.amount_exonerated
                + inv.amount_not_subject
                + inv.amount_without_right_to_credit
            )
            t_inventario += costo_neto
            t_iva_inv += sign * inv.vat_amount
            t_igtf_inv += sign * inv.igtf_amount
            t_cxp_inv += sign * inv.total_purchase

        # ---------------------------------------------------------------------
        # FASE 2: Acumulación de Bienes, Servicios
        # ---------------------------------------------------------------------
        t_gasto_by_account: Dict[str, Decimal] = {}
        t_iva_rest = Decimal("0.00")
        t_igtf_rest = Decimal("0.00")
        t_cxp_rest = Decimal("0.00")

        remaining_categories = [
            PurchaseLedgerInvoice.InvoiceCategory.BIENES,
            PurchaseLedgerInvoice.InvoiceCategory.SERVICIO,
            PurchaseLedgerInvoice.InvoiceCategory.SERVICIO_MIXTO,
        ]
        remaining_invoices = batch_invoices.filter(invoicecategory__in=remaining_categories)

        for inv in remaining_invoices:
            # Validación estricta de affected_accounts
            affected_list = inv.affected_accounts or []
            if not affected_list:
                raise ValidationError(
                    f"Fallo de Imputación Contable: La factura N° {inv.number} "
                    f"(Categoría: {inv.invoicecategory}) no posee cuentas afectadas (affected_accounts)."
                )

            sign = Decimal("1.00") if inv.document_type in [
                PurchaseLedgerInvoice.DocumentType.INVOICE,
                PurchaseLedgerInvoice.DocumentType.DEBIT_NOTE,
            ] else Decimal("-1.00")

            # Cálculo sin discriminar el IVA según derecho a crédito fiscal
            costo_neto = sign * (
                inv.taxable_base
                + inv.exempt_amount
                + inv.amount_exonerated
                + inv.amount_not_subject
                + inv.amount_without_right_to_credit
            )
            
            t_iva_rest += sign * inv.vat_amount
            t_igtf_rest += sign * inv.igtf_amount

            # Pasivo Proveedor Neto (Sin retención ISLR en esta fase)
            t_cxp_rest += sign * inv.total_purchase

            # Imputación a cuentas contables específicas
            for item in affected_list:
                acc_id = str(item["account_id"])
                item_amt = Decimal(str(item["amount"])) * sign
                t_gasto_by_account[acc_id] = t_gasto_by_account.get(acc_id, Decimal("0.00")) + item_amt

        # ---------------------------------------------------------------------
        # FASE 3: Generación del Asiento 1 (Resumen General de Compras)
        # ---------------------------------------------------------------------
        t_iva_total = t_iva_inv + t_iva_rest
        t_igtf_total = t_igtf_inv + t_igtf_rest
        t_cxp_total = t_cxp_inv + t_cxp_rest

        # Control de Desbalance (Partida Doble)
        suma_debe = t_inventario + sum(t_gasto_by_account.values()) + t_iva_total + t_igtf_total
        suma_haber = t_cxp_total

        if abs(suma_debe - suma_haber) > Decimal("0.01"):
            raise ValidationError(
                f"Desbalance en Asiento 1 de Compras: DEBE ({suma_debe}) != HABER ({suma_haber})."
            )

        # Creación con la fecha y hora del procesamiento actual
        asiento_1 = JournalEntryModel.objects.create(
            ledger=self.ledger,
            timestamp=timezone.now(),
            description=f"Asiento Resumen de Compras - Período {self.fiscal_period}",
            activity="operating",
        )

        # Registrar Movimientos en el DEBE
        if t_inventario > 0:
            TransactionModel.objects.create(
                journal_entry=asiento_1,
                account=self.fiscal_profile.inventory_account,
                tx_type="debit",
                amount=t_inventario,
                description="Costo de Inventario de Mercancía",
            )

        for acc_id, amount in t_gasto_by_account.items():
            if amount > 0:
                acc_obj = AccountModel.objects.get(pk=acc_id)
                TransactionModel.objects.create(
                    journal_entry=asiento_1,
                    account=acc_obj,
                    tx_type="debit",
                    amount=amount,
                    description="Costo / Gasto por Compras de Bienes y Servicios",
                )

        if t_iva_total > 0:
            TransactionModel.objects.create(
                journal_entry=asiento_1,
                account=self.fiscal_profile.vat_credit_account,
                tx_type="debit",
                amount=t_iva_total,
                description="IVA Crédito Fiscal Computable",
            )

        if t_igtf_total > 0:
            TransactionModel.objects.create(
                journal_entry=asiento_1,
                account=self.fiscal_profile.igtf_expense_account,
                tx_type="debit",
                amount=t_igtf_total,
                description="IGTF Pagado en Compras",
            )

        # Registrar Movimientos en el HABER
        if t_cxp_total > 0:
            TransactionModel.objects.create(
                journal_entry=asiento_1,
                account=self.fiscal_profile.cxp_suppliers_account,
                tx_type="credit",
                amount=t_cxp_total,
                description="Pasivo Comercial Cuentas por Pagar Proveedores",
            )

        # Verificación del Asiento 1
        txs_qs, is_valid_1 = asiento_1.verify()
        if not is_valid_1:
            raise ValidationError("Error de cuadratura en Asiento 1 (Partida Doble).")

        # ---------------------------------------------------------------------
        # FASE 4: Retenciones de IVA y Asiento 2
        # ---------------------------------------------------------------------
        asiento_2 = None
        if self.fiscal_profile.taxpayer_type == FiscalProfile.TaxpayerType.SPECIAL:
            vat_invoices = batch_invoices.filter(vat_amount__gt=Decimal("0.00"))
            t_iva_retenido = Decimal("0.00")

            for inv_vat in vat_invoices:
                cert_vat = VatWithholdingCertificate.objects.filter(
                    purchase_invoice=inv_vat,
                    fiscal_profile=self.fiscal_profile,
                    status=VatWithholdingCertificate.CertificateStatus.PRELIMINARY,
                ).first()

                if not cert_vat:
                    raise ValidationError(
                        f"Auditoría Fiscal Fallida: La factura N° {inv_vat.number} tiene IVA "
                        "pero no posee un Comprobante de Retención de IVA preliminar activo."
                    )

                sign_vat = Decimal("1.00") if inv_vat.document_type in [
                    PurchaseLedgerInvoice.DocumentType.INVOICE,
                    PurchaseLedgerInvoice.DocumentType.DEBIT_NOTE,
                ] else Decimal("-1.00")

                t_iva_retenido += sign_vat * cert_vat.vat_withheld_amount

            if t_iva_retenido > Decimal("0.00"):
                asiento_2 = JournalEntryModel.objects.create(
                    ledger=self.ledger,
                    timestamp=timezone.now(),
                    description=f"Asiento Resumen Retenciones de IVA - Período {self.fiscal_period}",
                    activity="operating",
                )

                # DEBE: Rebaja de Pasivo Proveedores
                TransactionModel.objects.create(
                    journal_entry=asiento_2,
                    account=self.fiscal_profile.cxp_suppliers_account,
                    tx_type="debit",
                    amount=t_iva_retenido,
                    description="Rebaja de Pasivo Comercial por Retención de IVA",
                )

                # HABER: Pasivo Fiscal por Enterar
                TransactionModel.objects.create(
                    journal_entry=asiento_2,
                    account=self.fiscal_profile.vat_withheld_payable_account,
                    tx_type="credit",
                    amount=t_iva_retenido,
                    description="Pasivo Fiscal IVA Retenido por Enterar",
                )

                txs_qs_2, is_valid_2 = asiento_2.verify()
                if not is_valid_2:
                    raise ValidationError("Error de cuadratura en Asiento 2 (Partida Doble).")

        # ---------------------------------------------------------------------
        # FASE 5: Retenciones de ISLR y Asiento 3
        # ---------------------------------------------------------------------
        asiento_3 = None
        t_islr_total = Decimal("0.00")

        islr_certs = IslrWithholdingCertificate.objects.filter(
            purchase_invoice__in=batch_invoices,
            fiscal_profile=self.fiscal_profile,
        )

        for cert in islr_certs:
            inv_islr = cert.purchase_invoice
            sign_islr = Decimal("1.00") if inv_islr.document_type in [
                PurchaseLedgerInvoice.DocumentType.INVOICE,
                PurchaseLedgerInvoice.DocumentType.DEBIT_NOTE,
            ] else Decimal("-1.00")

            t_islr_total += sign_islr * cert.islr_withheld_amount

        if t_islr_total > Decimal("0.00"):
            asiento_3 = JournalEntryModel.objects.create(
                ledger=self.ledger,
                timestamp=timezone.now(),
                description=f"Asiento Resumen Retenciones de ISLR - Período {self.fiscal_period}",
                activity="operating",
            )

            # DEBE: Rebaja de Pasivo Proveedores
            TransactionModel.objects.create(
                journal_entry=asiento_3,
                account=self.fiscal_profile.cxp_suppliers_account,
                tx_type="debit",
                amount=t_islr_total,
                description="Rebaja de Pasivo Comercial por Retención de ISLR",
            )

            # HABER: Pasivo Fiscal por Enterar (ISLR)
            TransactionModel.objects.create(
                journal_entry=asiento_3,
                account=self.fiscal_profile.islr_payable_account,
                tx_type="credit",
                amount=t_islr_total,
                description="Retenciones de ISLR por Pagar",
            )

            txs_qs_3, is_valid_3 = asiento_3.verify()
            if not is_valid_3:
                raise ValidationError("Error de cuadratura en Asiento 3 (Partida Doble).")

        # ---------------------------------------------------------------------
        # FASE FINAL: Transición de Estados
        # ---------------------------------------------------------------------
        batch_invoices.update(status=PurchaseLedgerInvoice.InvoiceStatus.PROCESSED)

        IslrWithholdingCertificate.objects.filter(
            purchase_invoice__in=batch_invoices
        ).update(status=IslrWithholdingCertificate.CertificateStatus.PROCESSED)

        VatWithholdingCertificate.objects.filter(
            purchase_invoice__in=batch_invoices
        ).update(status=VatWithholdingCertificate.CertificateStatus.PROCESSED)
        
        # Filtro y actualización de documentos con estatus ANULLED
        PurchaseLedgerInvoice.objects.filter(
            fiscal_profile=self.fiscal_profile,
            fiscal_period=self.fiscal_period,
            status=PurchaseLedgerInvoice.InvoiceStatus.ANULLED
        ).update(status=PurchaseLedgerInvoice.InvoiceStatus.ANULLED_PROCESSED)

        return asiento_1, asiento_2, asiento_3