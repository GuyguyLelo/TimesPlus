from django.urls import path

from apps.agents import views

app_name = "agents"

urlpatterns = [
    path("agents/", views.AgentListView.as_view(), name="list"),
    path("agents/referentiel/", views.ReferentielView.as_view(), name="referentiel"),
    path("agents/nouveau/", views.AgentCreateView.as_view(), name="create"),
    path("agents/<int:pk>/", views.AgentDetailView.as_view(), name="detail"),
    path("agents/<int:pk>/photo/", views.agent_photo, name="photo"),
    path("agents/<int:pk>/photo/modifier/", views.AgentPhotoUpdateView.as_view(), name="photo_update"),
    path("agents/<int:pk>/modifier/", views.AgentUpdateView.as_view(), name="update"),
    path("agents/<int:pk>/supprimer/", views.AgentDeleteView.as_view(), name="delete"),
]
