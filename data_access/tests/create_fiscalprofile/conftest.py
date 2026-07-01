"""Módulo de configuración de fixtures de pytest para modelos de acceso a datos.

Proporciona componentes altamente reutilizables y limpios para la inicialización
de usuarios administradores y conjuntos de datos fiscales estándar válidos.
"""

from typing import Dict, Any
import pytest
from django.contrib.auth.models import User
from data_access.models.base import FiscalProfile


@pytest.fixture
def db_admin(db: Any) -> User:
    """Fixture que provee un usuario administrador persistido en la base de datos.

    Args:
        db: Fixture nativo de pytest-django para habilitar el acceso a la BD.

    Returns:
        User: Instancia de un usuario de Django.
    """
    return User.objects.create_user(
        username="admin_test",
        email="admin@empresa.com",
        password="secure_password_123",
    )


@pytest.fixture
def valid_profile_data() -> Dict[str, Any]:
    """Fixture que provee un diccionario con datos fiscales válidos.

    Cumple estrictamente con las longitudes máximas y formatos del modelo.

    Returns:
        Dict[str, Any]: Estructura con parámetros obligatorios y opcionales.
    """
    return {
        "entity_name": "Corporación de Alimentos S.A.",
        "use_accrual_method": True,
        "fy_start_month": 1,
        "rif": "J-31234567-8",
        "code": "CTRL-2026-001",
        "taxpayer_type": FiscalProfile.TaxpayerType.ORDINARY,
        "nit": "0102030405",
    }