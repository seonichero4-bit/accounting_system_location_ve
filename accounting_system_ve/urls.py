from django.contrib import admin
from django.urls import path
from presentation.views import supplier
from presentation.views import fiscal_profile
from presentation.views import purchase_book

urlpatterns = [
    # URLS de Proveedores
    path("suppliers/", supplier.LocalSupplierListView.as_view(), name="supplier-list"),
    path("suppliers/new/", supplier.LocalSupplierCreateView.as_view(), name="supplier-create"),
    path("suppliers/<str:code>/", supplier.LocalSupplierDetailView.as_view(), name="supplier-detail"),
    path("suppliers/<str:code>/edit/", supplier.LocalSupplierUpdateView.as_view(), name="supplier-update"),
    path("suppliers/<str:code>/delete/", supplier.LocalSupplierDeleteView.as_view(), name="supplier-delete"),
    
    # URLS de Perfiles Fiscales
    path("fiscal-profiles/", fiscal_profile.FiscalProfileListView.as_view(), name="fiscal-profile-list"),
    path("fiscal-profiles/new/", fiscal_profile.FiscalProfileCreateView.as_view(), name="fiscal-profile-create"),
    path("fiscal-profiles/<str:code>/", fiscal_profile.FiscalProfileDetailView.as_view(), name="fiscal-profile-detail"),
    path("fiscal-profiles/<str:code>/edit/", fiscal_profile.FiscalProfileUpdateView.as_view(), name="fiscal-profile-update"),
    path("fiscal-profiles/<str:code>/delete/", fiscal_profile.FiscalProfileDeleteView.as_view(), name="fiscal-profile-delete"),

    # URLS de Libro de Compras
    path("purchase-invoices/", purchase_book.PurchaseLedgerInvoiceListView.as_view(), name="purchase-invoice-list"),
    path("purchase-invoices/new/", purchase_book.PurchaseLedgerInvoiceCreateView.as_view(), name="purchase-invoice-create"),
    path("purchase-invoices/<int:pk>/", purchase_book.PurchaseLedgerInvoiceDetailView.as_view(), name="purchase-invoice-detail"),
    path("purchase-invoices/<int:pk>/edit/", purchase_book.PurchaseLedgerInvoiceUpdateView.as_view(), name="purchase-invoice-update"),
    path("purchase-invoices/<int:pk>/delete/", purchase_book.PurchaseLedgerInvoiceDeleteView.as_view(), name="purchase-invoice-delete"),
]



