from typing import Any

from django.utils.functional import SimpleLazyObject, empty

def unwrap_lazy_object(obj: Any) -> Any:
    """Fuerza la evaluación de un SimpleLazyObject y devuelve la instancia real."""
    if isinstance(obj, SimpleLazyObject):
        if obj._wrapped is empty:
            obj._setup()  # Ejecuta la lambda interna (get_fiscal_period)
        return obj._wrapped
    return obj