from django.urls import path

from apps.workflow import views

app_name = "workflow"

urlpatterns = [
    path("validation/", views.ValidationQueueView.as_view(), name="queue"),
    path("validation/historique/", views.ValidationHistoryView.as_view(), name="history"),
    path("validation/<int:pk>/", views.ValidationDetailView.as_view(), name="detail"),
    path("validation/<int:pk>/approuver/", views.ApproveView.as_view(), name="approve"),
    path("validation/<int:pk>/rejeter/", views.RejectView.as_view(), name="reject"),
]
