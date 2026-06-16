from typing import Any
from django import forms
from django.forms import inlineformset_factory

# Se asume la existencia de estos modelos en la capa de datos
from accounting_system_ve.data_access.models.purchase_book import LibroComprasFactura, LineaFacturaCompra

class LibroComprasFacturaForm(forms.ModelForm):
    """
    Formulario de cabecera para el registro en el Libro de Compras.
    
    Mapea estrictamente los campos requeridos para la identificación del 
    documento fiscal, excluyendo de forma implícita (al usar 'fields') 
    cualquier campo autocalculado como totales o montos base.
    """
    
    class Meta:
        model = LibroComprasFactura
        fields = [
            'tipo_documento', 
            'numero', 
            'control_factura', 
            'fecha', 
            'tipo_compra'
        ]


# Factory para inyección dinámica de múltiples filas de detalle contable y comercial.
# Permite mantener la integridad referencial (Cabecera -> Líneas) en la interfaz.
LineaFacturaCompraFormSet = inlineformset_factory(
    parent_model=LibroComprasFactura,
    model=LineaFacturaCompra,
    fields=[
        'descripcion', 
        'precio_unitario', 
        'unidades', 
        'porcentaje_descuento', 
        'alicuota_iva', 
        'naturaleza', 
        'aplica_retencion_islr', 
        'porcentaje_retencion_islr', 
        'mapeo_contable'
    ],
    extra=1,
    can_delete=True
)