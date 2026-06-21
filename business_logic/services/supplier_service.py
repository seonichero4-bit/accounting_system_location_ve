"""Módulo de servicios para la gestión de proveedores.

Implementa la capa de servicios (Service Layer) encargada de encapsular
la lógica de negocio transaccional y las reglas de validación de proveedores,
manteniendo los modelos y controladores limpios.
"""

from typing import Tuple, Dict, Any

from data_access.models.base import FiscalProfile
from data_access.models.supplier import LocalSupplier


class SupplierService:
    """Servicio encargado de coordinar la lógica de negocio para los proveedores.

    Actúa como intermediario aislando la lógica específica del inquilino mediante
    la inyección del perfil fiscal en su inicialización.
    """

    def __init__(self, fiscal_profile: FiscalProfile) -> None:
        """Inicializa el servicio vinculándolo al perfil fiscal del inquilino activo.

        Args:
            fiscal_profile (FiscalProfile): La instancia del perfil fiscal bajo
                el cual se ejecutarán las operaciones de este servicio.
        """
        self.fiscal_profile = fiscal_profile

    def register_or_retrieve_local(
        self, supplier_data: Dict[str, Any]
    ) -> Tuple[LocalSupplier, bool]:
        """Registra un nuevo proveedor local o devuelve el existente si su RIF coincide.

        Implementa una lógica segura de creación (idempotente) delegando la
        búsqueda y la instanciación a los métodos de fábrica del modelo asociado
        al perfil fiscal.

        Args:
            datos_proveedor (Dict[str, Any]): Diccionario con los atributos necesarios
                para instanciar el proveedor (debe incluir la clave 'rif').

        Returns:
            Tuple[ProveedorLocal, bool]: Una tupla que contiene la instancia del
                proveedor (sea nueva o recuperada) y un booleano que es `True` si
                el registro fue creado en esta ejecución, o `False` si ya existía.
        """
        rif = supplier_data.get("rif")
        
        if rif:
            existing = self.fiscal_profile.get_supplier_by_rif(rif=rif)
            if existing:
                return existing, False  # No fue creado, ya existía

        # Si no existe, lo crea usando la lógica de fábrica delegada
        if isinstance(supplier_data.get("name"), str):
            new_supplier = self.fiscal_profile.create_supplier(**supplier_data)
            return new_supplier, True
        else: 
            raise TypeError("El campo 'name' debe ser una cadena de texto.")
        
     