import json
from django.views import View
from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages

from presentation.mixins import FiscalTenantMixin  
from business_logic.services.chartofaccountsImportservice import ChartOfAccountsImportService


class UploadChartOfAccountsView(FiscalTenantMixin, View):
    """Vista para recibir, validar e importar el archivo JSON con el Plan de Cuentas."""

    def post(self, request, *args, **kwargs):
        fiscal_profile = self.get_fiscal_profile()  #[cite: 3]

        if not fiscal_profile:
            return JsonResponse({'error': 'No se encontró un perfil fiscal activo para el inquilino actual.'}, status=404)

        if not fiscal_profile.entity:
            return JsonResponse({'error': 'El perfil fiscal no posee una entidad de Django Ledger vinculada.'}, status=400)

        # Verificación previa con la API nativa de django-ledger
        if fiscal_profile.entity.get_coa_model_qs().exists():
            return JsonResponse({'error': 'El inquilino ya posee un Plan de Cuentas (CoA) configurado.'}, status=400)

        # Validación de la presencia del archivo subido
        if 'json_file' not in request.FILES:
            return JsonResponse({'error': 'No se adjuntó ningún archivo'}, status=400)

        uploaded_file = request.FILES['json_file']

        if not uploaded_file.name.endswith('.json'):
            return JsonResponse({'error': 'El archivo debe tener extensión .json'}, status=400)

        try:
            data = json.load(uploaded_file)

            if not isinstance(data, list):
                return JsonResponse({'error': 'El archivo JSON debe contener una lista de cuentas.'}, status=400)

            # Procesa la importación a través del servicio
            service = ChartOfAccountsImportService(fiscal_profile=fiscal_profile)
            count = service.import_accounts_from_data(data)

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'exito', 'registros_procesados': count})

            messages.success(request, f'Se han importado exitosamente {count} cuentas al Plan de Cuentas.')
            return redirect('fiscal-profile-detail', pk=fiscal_profile.pk)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'El archivo contiene un JSON con sintaxis inválida'}, status=400)
        except UnicodeDecodeError:
            return JsonResponse({'error': 'El archivo debe estar codificado en UTF-8'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Error al procesar la importación: {str(e)}'}, status=500)