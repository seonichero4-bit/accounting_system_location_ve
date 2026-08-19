from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.core.exceptions import ValidationError

# Asumiendo las rutas de importación de tu proyecto
from business_logic.services.fiscalbatchprocessingservice import FiscalBatchProcessingService
from utils import unwrap_lazy_object

class FiscalBatchProcessingView(View):
    template_name = 'purchase_book.html'

    def get(self, request, *args, **kwargs):
        """Renderiza la interfaz para iniciar el procesamiento."""
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        """Maneja la invocación del servicio de procesamiento en lote."""
        
        # 1. Extraer y desenvolver los objetos perezosos del request
        fiscal_profile = unwrap_lazy_object(request.fiscal_profile)
        fiscal_period = unwrap_lazy_object(request.fiscal_period)
        
        try:
            # 2. Instanciar el servicio con los parámetros extraídos
            service = FiscalBatchProcessingService(
                fiscal_profile=fiscal_profile, 
                fiscal_period=fiscal_period
            )
            
            # 3. Ejecutar el procesamiento (puede devolver hasta 3 asientos contables)
            asiento_1, asiento_2, asiento_3 = service.execute_batch_processing()
            
            # Mensaje de éxito si todo salió bien
            messages.success(
                request, 
                f"Procesamiento del lote fiscal para el período {fiscal_period} completado con éxito."
            )
            
        except ValidationError as e:
            # 4. Manejo de excepciones lanzadas por el servicio
            # Se convierte la excepción a string para mostrarla de forma legible
            messages.error(request, str(e.message if hasattr(e, 'message') else e.messages[0] if hasattr(e, 'messages') else e))
        except Exception as e:
            # Manejo de fallos inesperados
            messages.error(request, f"Ocurrió un error inesperado: {str(e)}")
            
        # Refrescar la página después del procesamiento
        return redirect('fiscal-batch-process')