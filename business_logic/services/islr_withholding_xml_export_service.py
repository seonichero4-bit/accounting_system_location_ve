import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from typing import Tuple, Optional

from django.db.models import QuerySet
from data_access.models.concep_payment_islr.concepts_payment_pjd import IslrPjdChoices
from data_access.models.concep_payment_islr.concepts_payment_pjnd import IslrPjndChoices
from data_access.models.concep_payment_islr.concepts_payment_pnnr import IslrPnnrChoices
from data_access.models.concep_payment_islr.concepts_payment_pnr import IslrPnrChoices
from data_access.models.islr_withholding import IslrWithholdingCertificate


class IslrXmlGeneratorService:
    """
    Servicio encargado de construir la estructura XML del reporte consolidado de 
    retenciones de ISLR a partir de un perfil fiscal y período específico.
    """

    def __init__(self, fiscal_profile: any, fiscal_period: date) -> None:
        self.fiscal_profile = fiscal_profile
        self.fiscal_period = fiscal_period

    def get_queryset(self) -> QuerySet[IslrWithholdingCertificate]:
        """Obtiene y optimiza la consulta de certificados para el período fiscal."""
        return (
            IslrWithholdingCertificate.objects.filter(
                fiscal_profile=self.fiscal_profile,
                fiscal_period=self.fiscal_period,
            )
            .select_related("purchase_invoice__supplier")
            .order_by("application_date", "document_number")
        )

    def _resolve_concept_properties(
        self, cert: IslrWithholdingCertificate
    ) -> Tuple[str, str]:
        """
        Identifica la opción de concepto configurada en el comprobante 
        y extrae el código SENIAT y el porcentaje de retención.
        """
        concept_mapping = [
            (cert.concepts_payment_pnr, IslrPnrChoices),
            (cert.concepts_payment_pnnr, IslrPnnrChoices),
            (cert.concepts_payment_pjd, IslrPjdChoices),
            (cert.concepts_payment_pjnd, IslrPjndChoices),
        ]

        for val, choice_cls in concept_mapping:
            if val is not None:
                instance = choice_cls(val)
                raw_pct = instance.percentage
                
                # Formateo de alícuota: 0.03 -> 3, 0.01 -> 1
                if isinstance(raw_pct, Decimal):
                    pct_calculated = raw_pct * Decimal("100")
                    pct_str = (
                        f"{pct_calculated:.2f}".rstrip("0").rstrip(".")
                        if pct_calculated % 1 != 0
                        else str(int(pct_calculated))
                    )
                else:
                    pct_str = str(raw_pct)

                return instance.code, pct_str

        raise ValueError(
            f"El comprobante ID {cert.id} no posee ningún concepto de ISLR asignado."
        )

    def generate_xml_bytes(self) -> bytes:
        """
        Construye el árbol XML mediante ElementTree y retorna la serialización en bytes.
        """
        periodo_str = self.fiscal_period.strftime("%Y%m")
        rif_empresa = getattr(self.fiscal_profile, "rif", "")

        # Declaración de etiqueta raíz
        root = ET.Element(
            "RelacionRetencionesISLR",
            attrib={"RIFEmpresa": rif_empresa, "Periodo": periodo_str},
        )

        queryset = self.get_queryset()

        for cert in queryset:
            invoice = cert.purchase_invoice
            supplier = getattr(invoice, "supplier", None)
            
            code_concept, percentage_retention = self._resolve_concept_properties(cert)

            # Saneamiento de campos con reglas de negocio
            rif_retenido = supplier.rif.upper() if supplier and supplier.rif else ""
            
            raw_invoice_num = invoice.number if invoice and invoice.number else "0"
            numero_factura = raw_invoice_num[-10:]

            raw_control_num = (
                invoice.invoice_control if invoice and invoice.invoice_control else "NA"
            )
            numero_control = raw_control_num[-10:]

            fecha_operacion = cert.application_date.strftime("%d/%m/%Y")
            monto_operacion = f"{cert.service_amount:.2f}"

            # Construcción de la estructura interna <DetalleRetencion>
            detalle = ET.SubElement(root, "DetalleRetencion")
            ET.SubElement(detalle, "RifRetenido").text = rif_retenido
            ET.SubElement(detalle, "NumeroFactura").text = numero_factura
            ET.SubElement(detalle, "NumeroControl").text = numero_control
            ET.SubElement(detalle, "FechaOperacion").text = fecha_operacion
            ET.SubElement(detalle, "CodigoConcepto").text = code_concept
            ET.SubElement(detalle, "MontoOperacion").text = monto_operacion
            ET.SubElement(detalle, "PorcentajeRetencion").text = percentage_retention

        return ET.tostring(root, encoding="utf-8", xml_declaration=True)