"""Módulo de servicio para la exportación fiscal de retenciones de IVA.

Implementa la clase encargada de recuperar y transformar los comprobantes 
de retención en un stream binario de formato Excel, sin persistencia local,
cumpliendo con la normativa del SENIAT y la arquitectura aislada (multitenant).
"""

import io
from datetime import date
from typing import Any

import openpyxl

from data_access.models.purchase_book import PurchaseLedgerInvoice
from data_access.models.vat_withholding import VatWithholdingCertificate
from utils import unwrap_lazy_object


class VatWithholdingExcelExportService:
    """Servicio de generación del reporte Excel para comprobantes de retención de IVA.

    Encapsula la extracción (con mitigación N+1 mediante eager loading) y
    la transformación fila a fila de los datos tributarios, inyectando los 
    resultados en una hoja de cálculo sin alterar estilos ni formatos.
    """

    def __init__(self, fiscal_profile: Any, fiscal_period: Any) -> None:
        """Inicializa el servicio asegurando la integridad de las dependencias inyectadas.

        Args:
            fiscal_profile (Any): Perfil fiscal (tenant) para aislar la exportación.
            fiscal_period (Any): Periodo fiscal (generalmente date) a exportar.

        Raises:
            ValueError: Si alguna de las dependencias requeridas se provee como None.
        """
        self.fiscal_profile = unwrap_lazy_object(fiscal_profile)
        self.fiscal_period = unwrap_lazy_object(fiscal_period)

        if not self.fiscal_profile or not self.fiscal_period:
            raise ValueError(
                "Se requieren dependencias no nulas para 'fiscal_profile' y 'fiscal_period'."
            )

    def generate_excel_stream(self) -> io.BytesIO:
        """Construye y exporta en memoria volátil los comprobantes del periodo.

        Estructura el archivo mapeando 16 columnas obligatorias (A a P)
        según lo delimitado por los requerimientos técnicos y legales.

        Returns:
            io.BytesIO: Buffer de bytes que contiene el libro Excel. 
                        El puntero de lectura se encuentra posicionado al inicio (0).
        """
        # 1. Creación en memoria del Workbook sin persistencia en disco
        wb = openpyxl.Workbook()
        ws = wb.active

        # 2. Extracción optimizada (Eager Loading para prevenir N+1 Problem)
        queryset = (
            VatWithholdingCertificate.objects.filter(
                fiscal_profile=self.fiscal_profile,
                fiscal_period=self.fiscal_period
            )
            .select_related(
                'purchase_invoice',
                'purchase_invoice__supplier',
                'purchase_invoice__affected_invoice'
            )
            .order_by('application_date', 'document_number')
        )

        # Mapeo de valores base para los Enums
        doc_type_mapping = {
            PurchaseLedgerInvoice.DocumentType.INVOICE: "01",
            PurchaseLedgerInvoice.DocumentType.DEBIT_NOTE: "02",
            PurchaseLedgerInvoice.DocumentType.CREDIT_NOTE: "03",
        }

        # 3. Iteración y Construcción Fila a Fila
        for cert in queryset:
            invoice = cert.purchase_invoice

            # Transformación condicional de Alícuota
            try:
                aliquot_enum = PurchaseLedgerInvoice.VatPercentageChoices(invoice.vat_percentage)
                aliquot = float(aliquot_enum.as_decimal)
            except ValueError:
                aliquot = 0.0

            # Transformación condicional de Documento Afectado y Expediente
            affected_invoice_number = (
                invoice.affected_invoice.number if invoice.affected_invoice else "0"
            )
            import_file = (
                invoice.import_file_number if invoice.import_file_number else "0"
            )

            row = [
                cert.fiscal_profile.rif,                                   # Col A
                self.fiscal_period.strftime("%Y%m"),                       # Col B
                invoice.date,                                              # Col C
                "C",                                                       # Col D
                doc_type_mapping.get(invoice.document_type, "01"),         # Col E
                invoice.supplier.rif,                                      # Col F
                invoice.number,                                            # Col G
                invoice.invoice_control,                                   # Col H
                float(invoice.total_purchase or 0.0),                      # Col I
                float(invoice.taxable_base or 0.0),                        # Col J
                float(cert.vat_withheld_amount or 0.0),                    # Col K
                affected_invoice_number,                                   # Col L
                cert.document_number,                                      # Col M
                float(invoice.exempt_amount or 0.0),                       # Col N
                aliquot,                                                   # Col O
                import_file                                                # Col P
            ]
            ws.append(row)

        # 4. Guardado en stream volátil y reseteo del puntero a 0
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        return buffer