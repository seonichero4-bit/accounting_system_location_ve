from django.contrib import admin
from django.urls import path
from presentation.views import supplier
from presentation.views import fiscal_profile
from presentation.views import purchase_book
from presentation.views import vat_withholding
from presentation.views import islr_withholding

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

    # ==========================================
    # URLS de Comprobantes de Retención de IVA
    # ==========================================
    
    # --- URLS Aisladas / Globales ---
    path("vat-withholdings/", vat_withholding.VatWithholdingCertificateListView.as_view(), name="vat-withholding-list"),
    path("vat-withholdings/<int:pk>/", vat_withholding.VatWithholdingCertificateDetailView.as_view(), name="vat-withholding-detail"),
    path("vat-withholdings/<int:pk>/delete/", vat_withholding.VatWithholdingCertificateDeleteView.as_view(), name="vat-withholding-delete"),

    # --- URLS Contextuales (Desde Factura Específica) ---
    path("purchase-invoices/<int:invoice_pk>/vat-withholding/new/", vat_withholding.VatWithholdingCertificateCreateView.as_view(), name="vat-withholding-create"),
    path("purchase-invoices/<int:invoice_pk>/vat-withholding/<int:pk>/edit/", vat_withholding.VatWithholdingCertificateUpdateView.as_view(), name="vat-withholding-update"),
    path("purchase-invoices/<int:invoice_pk>/vat-withholdings/", vat_withholding.VatWithholdingCertificateListView.as_view(), name="invoice-vat-withholding-list"),
    path("purchase-invoices/<int:invoice_pk>/vat-withholding/<int:pk>/", vat_withholding.VatWithholdingCertificateDetailView.as_view(), name="invoice-vat-withholding-detail"),
    path("purchase-invoices/<int:invoice_pk>/vat-withholding/<int:pk>/delete/", vat_withholding.VatWithholdingCertificateDeleteView.as_view(), name="invoice-vat-withholding-delete"),

    # ==========================================
    # URLS de Comprobantes de Retención de ISLR
    # ==========================================
    
    # --- URLS Aisladas / Globales ---
    path("islr-withholdings/", islr_withholding.IslrWithholdingCertificateListView.as_view(), name="islr-withholding-list"),
    path("islr-withholdings/<int:pk>/", islr_withholding.IslrWithholdingCertificateDetailView.as_view(), name="islr-withholding-detail"),
    path("islr-withholdings/<int:pk>/delete/", islr_withholding.IslrWithholdingCertificateDeleteView.as_view(), name="islr-withholding-delete"),

    # --- URLS Contextuales (Desde Factura Específica) ---
    path("purchase-invoices/<int:invoice_pk>/islr-withholding/new/", islr_withholding.IslrWithholdingCertificateCreateView.as_view(), name="islr-withholding-create"),
    path("purchase-invoices/<int:invoice_pk>/islr-withholding/<int:pk>/edit/", islr_withholding.IslrWithholdingCertificateUpdateView.as_view(), name="islr-withholding-update"),
    path("purchase-invoices/<int:invoice_pk>/islr-withholdings/", islr_withholding.IslrWithholdingCertificateListView.as_view(), name="invoice-islr-withholding-list"),
    path("purchase-invoices/<int:invoice_pk>/islr-withholding/<int:pk>/", islr_withholding.IslrWithholdingCertificateDetailView.as_view(), name="invoice-islr-withholding-detail"),
    path("purchase-invoices/<int:invoice_pk>/islr-withholding/<int:pk>/delete/", islr_withholding.IslrWithholdingCertificateDeleteView.as_view(), name="invoice-islr-withholding-delete"),
]



