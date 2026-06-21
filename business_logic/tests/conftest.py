"""Configuración de fixtures locales para la suite de pruebas de lógica de negocio.

Este módulo define de manera explícita y manual todos los fixtures requeridos
para las pruebas de integración y del ORM de Django, eliminando dependencias
de archivos de configuración externos y garantizando la autonomía de la suite.
"""
from typing import Any
import pytest

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django_ledger.models import EntityModel

from business_logic.services.supplier_service import SupplierService
from data_access.models.base import FiscalProfile
from data_access.models.supplier import LocalSupplier


@pytest.fixture
def test_user(db: Any) -> User:
    """Fixture que crea de forma manual un usuario del sistema.

    Args:
        db: Fixture nativo de pytest-django para habilitar acceso a la BD.

    Returns:
        User: Instancia de usuario autenticable en Django.
    """
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="usuario_test",
        password="SecurePassword123!"
    )


@pytest.fixture
def ledger_entity(db: Any, test_user: User) -> EntityModel:
    """Fixture que crea una entidad contable de django-ledger de forma manual.

    Args:
        db: Fixture nativo de pytest-django para habilitar acceso a la BD.
        test_user (User): Instancia del usuario administrador asignado.

    Returns:
        EntityModel: Instancia de la entidad contable base.
    """
    return EntityModel.create_entity(
        name=f"Empresa Base de Pruebas S.A",
        admin=test_user,
        use_accrual_method=True,
        fy_start_month=1
    )
    


@pytest.fixture
def fiscal_profile(db: Any, test_user: User, ledger_entity: EntityModel) -> FiscalProfile:
    """Fixture que crea un perfil fiscal venezolano asociado al inquilino contable.

    Args:
        db: Fixture nativo de pytest-django para habilitar acceso a la BD.
        test_user (User): Usuario titular.
        ledger_entity (EntityModel): Entidad contable asociada.

    Returns:
        FiscalProfile: Instancia de control fiscal multi-inquilino.
    """
    return FiscalProfile.objects.create(
        name="Perfil fiscal pruebas",
        rif="J-8235548-2",
        entity=ledger_entity
    )


@pytest.fixture
def existing_supplier(db: Any, fiscal_profile: FiscalProfile) -> LocalSupplier:
    """Fixture que da de alta un proveedor local existente en la base de datos.

    Args:
        db: Fixture nativo de pytest-django para habilitar acceso a la BD.
        fiscal_profile (FiscalProfile): Perfil fiscal donde se aloja el proveedor.

    Returns:
        LocalSupplier: Instancia del proveedor persistido con RIF estructurado.
    """
    return fiscal_profile.create_supplier(
        rif="J-12345678-9",
        name="Proveedor Preexistente C.A."
    )


@pytest.fixture
def supplier_service(fiscal_profile: FiscalProfile) -> SupplierService:
    """Fixture que inicializa el servicio inyectando el entorno fiscal real.

    Args:
        fiscal_profile (FiscalProfile): Instancia del perfil fiscal de pruebas.

    Returns:
        SupplierService: Componente de lógica de negocio listo para operar.
    """
    return SupplierService(fiscal_profile=fiscal_profile)