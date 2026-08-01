
class RequestScopedQuerySetMixin:
    """
    Mixin para CBVs (ListView, DetailView, UpdateView, DeleteView, CreateView).
    Garantiza que el QuerySet esté acotado por los datos del request actual.
    """
    def get_queryset(self):
        # 1. Obtiene el queryset base del modelo o la propiedad queryset de la vista
        qs = super().get_queryset() if hasattr(super(), 'get_queryset') else self.model.objects.all()
        
        # 2. Si el queryset implementa for_request, se delega el filtrado
        if hasattr(qs, 'for_request'):
            return qs.for_request(self.request)
            
        return qs