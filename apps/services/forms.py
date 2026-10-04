from django import forms

from apps.accounts.form_mixins import BootstrapFormMixin
from apps.services.models import Service


class ServiceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Service
        fields = ["code", "niveau", "nom", "description", "service_parent", "actif"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Service.objects.all()
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        self.fields["service_parent"].queryset = queryset.order_by("niveau", "code")
        self.fields["service_parent"].required = False
        self.fields["service_parent"].label_from_instance = (
            lambda item: f"{item.get_niveau_display()} — {item.code} — {item.nom}"
        )
        self.fields["niveau"].help_text = (
            "Direction générale, puis direction, division et bureau."
        )

    def clean_code(self):
        return (self.cleaned_data["code"] or "").strip().upper()
