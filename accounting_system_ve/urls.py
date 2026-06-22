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
from django.urls import path
from presentation.views import supplier

urlpatterns = [
    # urls_supplier
    path("suppliers/", supplier.LocalSupplierListView.as_view(), name="supplier-list"),
    path("suppliers/new/", supplier.LocalSupplierCreateView.as_view(), name="supplier-create"),
    path("suppliers/<str:code>/", supplier.LocalSupplierDetailView.as_view(), name="supplier-detail"),
    path("suppliers/<str:code>/edit/", supplier.LocalSupplierUpdateView.as_view(), name="supplier-update"),
    path("suppliers/<str:code>/delete/", supplier.LocalSupplierDeleteView.as_view(), name="supplier-delete"),
]