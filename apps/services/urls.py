from django.urls import path

from apps.services import views

app_name = "services"

urlpatterns = [
    path("services/", views.ServiceListView.as_view(), name="list"),
    path("services/nouveau/", views.ServiceCreateView.as_view(), name="create"),
    path("services/<int:pk>/", views.ServiceDetailView.as_view(), name="detail"),
    path("services/<int:pk>/modifier/", views.ServiceUpdateView.as_view(), name="update"),
    path("services/<int:pk>/activite/", views.ServiceActiviteView.as_view(), name="activite"),
    path("services/<int:pk>/supprimer/", views.ServiceDeleteView.as_view(), name="delete"),
]
