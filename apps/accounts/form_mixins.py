"""Mise en forme commune des formulaires Bootstrap."""

from django import forms


def apply_bootstrap(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            css = "form-check-input"
        elif isinstance(widget, forms.Select):
            css = "form-select"
        elif isinstance(widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
            css = ""
        else:
            css = "form-control"
        if css:
            current = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{current} {css}".strip()


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)
