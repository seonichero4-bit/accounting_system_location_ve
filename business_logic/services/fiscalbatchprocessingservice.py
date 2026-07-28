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
        application_month_year: str,
    ):
        """Inicializa el servicio con el perfil fiscal del inquilino y el período.

        Args:
            fiscal_profile: Instancia del modelo FiscalProfile con sus FKs
                            hacia LedgerModel y AccountModel configuradas.
            application_month_year: Período fiscal en formato MM-YYYY.
        """
        self.fiscal_profile = fiscal_profile
        self.application_month_year = application_month_year
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
    def execute_batch_processing(self) -> Tuple[JournalEntryModel, JournalEntryModel | None]:
        """Ejecuta el procesamiento atómico del lote y genera los asientos contables."""
        batch_invoices = PurchaseLedgerInvoice.objects.filter(
            fiscal_profile=self.fiscal_profile,
            application_month_year=self.application_month_year,
            status=PurchaseLedgerInvoice.InvoiceStatus.PRELIMINARY,
        )

        if not batch_invoices.exists():
            raise ValidationError(
                f"No existen facturas preliminares para el período {self.application_month_year}."
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
        # FASE 2: Acumulación de Bienes, Servicios e ISLR
        # ---------------------------------------------------------------------
        t_gasto_by_account: Dict[str, Decimal] = {}
        t_iva_rest = Decimal("0.00")
        t_igtf_rest = Decimal("0.00")
        t_islr = Decimal("0.00")
        t_cxp_rest = Decimal("0.00")

        remaining_categories = [
            PurchaseLedgerInvoice.InvoiceCategory.BIENES,
            PurchaseLedgerInvoice.InvoiceCategory.SERVICIO,
            PurchaseLedgerInvoice.InvoiceCategory.SERVICIO_MIXTO,
        ]
        remaining_invoices = batch_invoices.filter(invoicecategory__in=remaining_categories)

        for inv in remaining_invoices:
            # Requisito 3: Validación estricta de affected_accounts
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

            # Retención de ISLR
            islr_cert = IslrWithholdingCertificate.objects.filter(
                purchase_invoice=inv,
                fiscal_profile=self.fiscal_profile,
            ).first()

            r_k = (sign * islr_cert.islr_withheld_amount) if islr_cert else Decimal("0.00")
            t_islr += r_k

            # Tratamiento de IVA según derecho a crédito fiscal
            grants_credit = inv.purchase_type in [
                PurchaseLedgerInvoice.PurchaseType.INTERNAL,
                PurchaseLedgerInvoice.PurchaseType.IMPORT,
            ]

            if grants_credit:
                g_k = sign * (
                    inv.taxable_base
                    + inv.exempt_amount
                    + inv.amount_exonerated
                    + inv.amount_not_subject
                    + inv.amount_without_right_to_credit
                )
                v_k = sign * inv.vat_amount
            else:
                # IVA no deducible incrementa el costo/gasto
                g_k = sign * (
                    inv.taxable_base
                    + inv.exempt_amount
                    + inv.amount_exonerated
                    + inv.amount_not_subject
                    + inv.amount_without_right_to_credit
                    + inv.vat_amount
                )
                v_k = Decimal("0.00")

            t_iva_rest += v_k
            t_igtf_rest += sign * inv.igtf_amount

            # Pasivo Proveedor Neto
            p_k = (sign * inv.total_purchase) - r_k
            t_cxp_rest += p_k

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
        suma_haber = t_cxp_total + t_islr

        if abs(suma_debe - suma_haber) > Decimal("0.01"):
            raise ValidationError(
                f"Desbalance en Asiento 1 de Compras: DEBE ({suma_debe}) != HABER ({suma_haber})."
            )

        # Creación con la fecha y hora del procesamiento actual
        asiento_1 = JournalEntryModel.objects.create(
            ledger=self.ledger,
            timestamp=timezone.now(),
            description=f"Asiento Resumen de Compras - Período {self.application_month_year}",
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
        if t_islr > 0:
            TransactionModel.objects.create(
                journal_entry=asiento_1,
                account=self.fiscal_profile.islr_payable_account,
                tx_type="credit",
                amount=t_islr,
                description="Retenciones de ISLR por Pagar",
            )

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
        # FASE 4 Y 5: Retenciones de IVA y Asiento 2
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
                    description=f"Asiento Resumen Retenciones de IVA - Período {self.application_month_year}",
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
        # FASE FINAL: Transición de Estados
        # ---------------------------------------------------------------------
        batch_invoices.update(status=PurchaseLedgerInvoice.InvoiceStatus.PROCESSED)

        IslrWithholdingCertificate.objects.filter(
            purchase_invoice__in=batch_invoices
        ).update(status=IslrWithholdingCertificate.CertificateStatus.PROCESSED)

        VatWithholdingCertificate.objects.filter(
            purchase_invoice__in=batch_invoices
        ).update(status=VatWithholdingCertificate.CertificateStatus.PROCESSED)

        return asiento_1, asiento_2