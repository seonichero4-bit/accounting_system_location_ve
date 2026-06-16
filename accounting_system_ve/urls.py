"""
URL configuration for accounting_system_ve project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from fiscal_localization.presentation.views import supplier

urlpatterns = [
    # urls_supplier
    path("proveedores/", supplier.ProveedorLocalListView.as_view(), name="proveedor-list"),
    path("proveedores/nuevo/", supplier.ProveedorLocalCreateView.as_view(), name="proveedor-create"),
    path("proveedores/<int:pk>/", supplier.ProveedorLocalDetailView.as_view(), name="proveedor-detail"),
    path("proveedores/<int:pk>/editar/", supplier.ProveedorLocalUpdateView.as_view(), name="proveedor-update"),
    path("proveedores/<int:pk>/eliminar/", supplier.ProveedorLocalDeleteView.as_view(), name="proveedor-delete"),
]