from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("administration/utilisateurs/", views.UserListView.as_view(), name="users"),
    path("administration/utilisateurs/nouveau/", views.UserCreateView.as_view(), name="user_create"),
    path("administration/utilisateurs/<int:pk>/modifier/", views.UserUpdateView.as_view(), name="user_update"),
    path("administration/groupes/", views.GroupListView.as_view(), name="groups"),
    path("administration/groupes/<int:pk>/", views.GroupDetailView.as_view(), name="group_detail"),
]
