from django import forms

from apps.accounts.form_mixins import BootstrapFormMixin


class RejectForm(BootstrapFormMixin, forms.Form):
    commentaire = forms.CharField(
        label="Motif du rejet",
        widget=forms.Textarea(attrs={"rows": 4}),
        min_length=3,
    )


class ApproveForm(BootstrapFormMixin, forms.Form):
    commentaire = forms.CharField(
        label="Commentaire",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
