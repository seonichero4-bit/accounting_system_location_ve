"""Módulo de configuración de fixtures de pytest para la suite de pruebas del sistema fiscal.

Proporciona instancias reutilizables de usuarios administradores, clientes
autenticados y perfiles fiscales de prueba para simular el entorno multi-tenant.
"""

from typing import Any, Generator
import pytest
from django.contrib.auth.models import User
from django.test import Client
from data_access.models.base import FiscalProfile


@pytest.fixture
def admin_user(db: Any) -> User:
    """Fixture que crea y retorna un usuario administrador estándar.

    Args:
        db (Any): Inyección de la base de datos de pytest-django.

    Returns:
        User: Instancia del usuario con privilegios administrativos.
    """
    return User.objects.create_user(
        username="admin_test",
        email="admin@empresa.com",
        password="securepassword123"
    )


@pytest.fixture
def auth_client(admin_user: User) -> Client:
    """Fixture que proporciona un cliente HTTP de Django autenticado.

    Args:
        admin_user (User): Instancia del usuario de pruebas.

    Returns:
        Client: Cliente de pruebas con sesión iniciada para el usuario.
    """
    client = Client()
    client.force_login(admin_user)
    return client


@pytest.fixture
def fiscal_profile_factory(db: Any, admin_user: User) -> Generator[Any, None, None]:
    """Factory fixture para instanciar perfiles fiscales válidos de manera dinámica.

    Args:
        db (Any): Inyección de la base de datos de pytest-django.
        admin_user (User): Usuario administrador dueño de las entidades.

    Yields:
        callable: Función auxiliar para la generación controlada de perfiles.
    """
    def _create_profile(
        entity_name: str = "Empresa Base S.A.",
        rif: str = "J123456780",
        taxpayer_type: str = "ORDINARY"
    ) -> FiscalProfile:
        """Crea un registro de perfil fiscal acoplado a una entidad de Django Ledger."""
        return FiscalProfile.create_profile(
            admin=admin_user,
            entity_name=entity_name,
            use_accrual_method=True,
            fy_start_month=1,
            rif=rif,
            taxpayer_type=taxpayer_type
        )
    return _create_profile