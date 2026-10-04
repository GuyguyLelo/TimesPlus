from django.urls import path

from apps.reports import views

app_name = "reports"

urlpatterns = [
    path("rapports/", views.ReportHubView.as_view(), name="hub"),
    path("rapports/mensuel/", views.MonthlyReportView.as_view(), name="monthly"),
    path("rapports/historique/", views.HistoricalReportView.as_view(), name="historical"),
    path("rapports/service/", views.ServiceReportView.as_view(), name="service"),
    path("rapports/agent/", views.AgentReportView.as_view(), name="agent"),
    path("rapports/export/excel/", views.ExportExcelView.as_view(), name="excel"),
    path("rapports/export/pdf/", views.ExportPdfView.as_view(), name="pdf"),
]
