from django.urls import path

from apps.audit import views

app_name = "audit"

urlpatterns = [
    path("audit/", views.AuditListView.as_view(), name="list"),
    path("audit/<int:pk>/", views.AuditDetailView.as_view(), name="detail"),
]
