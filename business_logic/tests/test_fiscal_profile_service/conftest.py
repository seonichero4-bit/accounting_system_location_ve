"""Módulo de configuración global de pruebas para la suite de servicios fiscales.

Define los fixtures compartidos y reutilizables de pytest necesarios para
validar el comportamiento del servicio FiscalProfileService utilizando la base
de datos PostgreSQL configurada en el entorno de Django.
"""

import pytest
from django.contrib.auth.models import User
from django_ledger.models import EntityModel

from data_access.models.base import FiscalProfile
from business_logic.services.fiscal_profile_service import FiscalProfileService


@pytest.fixture
def admin_user(db: None) -> User:
    """Fixture que provee un usuario administrador autenticado para las pruebas.

    Args:
        db (None): Fixture interno de pytest-django para habilitar el acceso a la BD.

    Returns:
        User: Instancia del usuario administrador creado en el sistema.
    """
    return User.objects.create_superuser(
        username="admin_test",
        email="admin@test.com",
        password="securepassword123"
    )


@pytest.fixture
def fiscal_profile_service(admin_user: User) -> FiscalProfileService:
    """Fixture que inicializa el servicio inyectando el usuario operador.

    Args:
        admin_user (User): Instancia del usuario administrador provista por su fixture.

    Returns:
        FiscalProfileService: Instancia del servicio lista para operar.
    """
    return FiscalProfileService(admin_user=admin_user)


@pytest.fixture
def sample_fiscal_profile(admin_user: User) -> FiscalProfile:
    """Fixture que genera un perfil fiscal base con su entidad asociada de forma válida.

    Args:
        admin_user (User): Instancia del usuario administrador.

    Returns:
        FiscalProfile: Instancia de FiscalProfile persistida en la base de datos.
    """
    return FiscalProfile.create_profile(
        admin=admin_user,
        entity_name="Empresa Matriz S.A.",
        use_accrual_method=True,
        fy_start_month=1,
        rif="J-12345678-0",
        code="CTRL-001",
        taxpayer_type="ORDINARY"
    )