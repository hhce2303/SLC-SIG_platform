from django.urls import path

from apps.codegen.views import (
    AuditApproveView,
    AuditDetailView,
    AuditListView,
    AuditRejectView,
    GenerateView,
)

urlpatterns = [
    path("generate/",                          GenerateView.as_view(),      name="codegen-generate"),
    path("audits/",                            AuditListView.as_view(),     name="codegen-audit-list"),
    path("audits/<int:audit_id>/",             AuditDetailView.as_view(),   name="codegen-audit-detail"),
    path("audits/<int:audit_id>/approve/",     AuditApproveView.as_view(),  name="codegen-audit-approve"),
    path("audits/<int:audit_id>/reject/",      AuditRejectView.as_view(),   name="codegen-audit-reject"),
]
