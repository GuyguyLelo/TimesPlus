from django.urls import path

from apps.overtime import views, views_referentiel

app_name = "overtime"

urlpatterns = [
    path("heures/", views.OvertimeListView.as_view(), name="mine"),
    path("heures/nouvelle/", views.OvertimeFormView.as_view(), name="create"),
    path("heures/paiement/", views.PayrollView.as_view(), name="payroll"),
    path("heures/paiement/cloturer/", views.PayrollCloseView.as_view(), name="payroll_close"),
    path("heures/agents/", views.search_agents, name="agent_search"),
    path("heures/listes/<int:pk>/signer/", views.signer_liste, name="sign_list"),
    path("heures/toutes/", views.AllOvertimeRedirectView.as_view(), name="all"),
    path("heures/apercu/", views.preview_calculation, name="preview"),
    path("heures/<int:pk>/", views.OvertimeDetailView.as_view(), name="detail"),
    path("heures/<int:pk>/modifier/", views.OvertimeFormView.as_view(), name="update"),
    path("heures/<int:pk>/supprimer/", views.OvertimeDeleteView.as_view(), name="delete"),
    path("heures/<int:pk>/soumettre/", views.OvertimeSubmitView.as_view(), name="submit"),
    path("heures/<int:pk>/pieces/", views.AddAttachmentView.as_view(), name="add_attachment"),
    path("heures/pieces/<int:pk>/telecharger/", views.download_attachment, name="attachment_download"),
    path("heures/pieces/<int:pk>/supprimer/", views.delete_attachment, name="attachment_delete"),
    path("horaires/", views_referentiel.ScheduleListView.as_view(), name="schedules"),
    path("horaires/nouveau/", views_referentiel.ScheduleCreateView.as_view(), name="schedule_create"),
    path("horaires/<int:pk>/modifier/", views_referentiel.ScheduleUpdateView.as_view(), name="schedule_update"),
    path("horaires/<int:pk>/supprimer/", views_referentiel.ScheduleDeleteView.as_view(), name="schedule_delete"),
    path("jours-feries/", views_referentiel.HolidayListView.as_view(), name="holidays"),
    path("jours-feries/nouveau/", views_referentiel.HolidayCreateView.as_view(), name="holiday_create"),
    path("jours-feries/<int:pk>/modifier/", views_referentiel.HolidayUpdateView.as_view(), name="holiday_update"),
    path("jours-feries/<int:pk>/supprimer/", views_referentiel.HolidayDeleteView.as_view(), name="holiday_delete"),
    path("administration/types/", views_referentiel.TypeListView.as_view(), name="types"),
    path("administration/types/nouveau/", views_referentiel.TypeCreateView.as_view(), name="type_create"),
    path("administration/types/<int:pk>/modifier/", views_referentiel.TypeUpdateView.as_view(), name="type_update"),
    path("administration/regles/", views_referentiel.RuleListView.as_view(), name="rules"),
    path("administration/regles/nouvelle/", views_referentiel.RuleCreateView.as_view(), name="rule_create"),
    path("administration/regles/<int:pk>/modifier/", views_referentiel.RuleUpdateView.as_view(), name="rule_update"),
    path("administration/regles/<int:pk>/supprimer/", views_referentiel.RuleDeleteView.as_view(), name="rule_delete"),
]
