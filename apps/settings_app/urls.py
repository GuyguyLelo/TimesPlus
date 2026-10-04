from django.urls import path

from apps.settings_app.views import ParametersView

app_name = "settings_app"

urlpatterns = [
    path("administration/parametres/", ParametersView.as_view(), name="parameters"),
]
