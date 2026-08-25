"""Módulo de vistas para la exportación de reportes fiscales.

Proporciona los controladores HTTP (Vistas) necesarios para orquestar
la descarga de archivos Excel con los comprobantes de retención de IVA,
conectando la capa de red con la lógica de negocio subyacente.
"""

from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.views import View

from business_logic.services.vat_withholding_excel_export_service import VatWithholdingExcelExportService
from utils import unwrap_lazy_object


class VatWithholdingExcelExportView(View):
    """Vista basada en clases para manejar la descarga del reporte de retenciones de IVA.

    Se encarga de extraer el contexto fiscal del request (inyectado previamente
    por middlewares o mixins), instanciar el servicio de exportación y construir
    la respuesta HTTP con los encabezados adecuados para forzar la descarga
    del archivo binario.
    """

    def get(self, request: HttpRequest, *args: tuple, **kwargs: dict) -> HttpResponse:
        """Procesa la solicitud GET para generar y retornar el archivo Excel.

        Extrae el perfil y periodo fiscal del request, desempaquetando los
        objetos perezosos (SimpleLazyObject). Si las dependencias no están
        presentes, retorna un error 400. En caso de éxito, retorna un 
        HttpResponse con el stream binario adjunto.

        Args:
            request (HttpRequest): Objeto de petición HTTP de Django.
            *args (tuple): Argumentos posicionales adicionales.
            **kwargs (dict): Argumentos de palabras clave adicionales.

        Returns:
            HttpResponse: Respuesta con el archivo adjunto o un error HTTP 400
                          si falta el contexto fiscal.
        """
        # 1. Extracción y desempaquetado de las dependencias inyectadas en el request
        fiscal_profile = unwrap_lazy_object(getattr(request, "fiscal_profile", None))
        fiscal_period = unwrap_lazy_object(getattr(request, "fiscal_period", None))

        # 2. Instanciación del servicio con manejo de dependencias faltantes
        try:
            export_service = VatWithholdingExcelExportService(
                fiscal_profile=fiscal_profile,
                fiscal_period=fiscal_period,
            )
        except ValueError as error_msg:
            return HttpResponseBadRequest(
                f"No se pudo procesar la exportación: {error_msg}"
            )

        # 3. Generación del stream binario
        excel_stream = export_service.generate_excel_stream()

        # 4. Formateo seguro del periodo para el nombre del archivo (YYYYMM)
        try:
            period_str = fiscal_period.strftime("%Y%m")
        except AttributeError:
            period_str = str(fiscal_period)

        filename = f"Retenciones_IVA_{period_str}.xlsx"

        # 5. Construcción de la respuesta HTTP configurada para descarga directa
        response = HttpResponse(
            excel_stream.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response