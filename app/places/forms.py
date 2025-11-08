# app/core/forms.py
from django import forms
from .models import Venue, Event
from django.forms import ModelForm
from django.utils.text import slugify


SPANISH_LABELS = {
    "Commune": "Comuna",
    "name": "Nombre",
    "category": "Categoría",
    "cover_image": "Imagen de portada",
    "vibe_tags": "Etiquetas de ambiente",
    "description": "Descripción",
    "min_age": "Edad mínima",
    "dress_code": "Código de vestimenta",
    "payment_methods": "Métodos de pago",
    "address": "Dirección",
    "phone": "Teléfono",
    "website": "Sitio web",
    "instagram": "Instagram",
    "reservation_url": "URL de reservas/entradas",
    "experience_venue": "Experiencia en el lugar",
    "hours_short": "Horarios (corto)",
    "highlights_1": "Destacados de la barra principal",
    "highlights_2": "Destacados de la barra secundario",
    "highlights_3": "Destacados de la barra secundario",
    "recommended_title": "Título recomendado",
    "recommended_body": "Detalle recomendado",
    "menu_pdf": "Menú (PDF)",
    "menu_qr_url": "QR del menú (URL)",
    "vgt_promos_1": "Promo 1",
    "vgt_promos_2": "Promo 2",
    "vgt_promos_3": "Promo 3",
    "gallery_venue": "Imagen de galería",
}

class LabelsMixin:
    """
    Aplica labels en español tomando los nombres de campo como claves.
    Puedes sobreescribir LABELS en un form concreto si necesitas ajustes.
    """
    LABELS = SPANISH_LABELS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplica los labels solo si el campo existe en el form
        for field_name, field in self.fields.items():
            if field_name in self.LABELS:
                field.label = self.LABELS[field_name]

class VenueForm(LabelsMixin ,forms.ModelForm):
    class Meta:
        model = Venue
        fields = [
            "cover_image", "description", "min_age", "dress_code",
            "payment_methods", "address", "phone", "website", "instagram",
            "reservation_url", "hours_short",
            "highlights_1","highlights_2","highlights_3", "recommended_title", "recommended_body",
            "menu_pdf", "menu_qr_url", "experience_venue",
            "vgt_promos_1", "vgt_promos_2", "vgt_promos_3",
            "vibe_tags",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "experience_venue": forms.Textarea(attrs={"rows": 2}),
            "vibe_tags": forms.SelectMultiple(attrs={"class": "d-none"}),
        }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

# forms.py
class VenueUpdateForm(LabelsMixin, ModelForm):
    class Meta:
        model = Venue
        fields = "__all__"
        exclude = ("owner_user", "slug", "is_published", "gallery_venue")  # 🔹 se agregó aquí

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # === Widgets específicos ===
        for name in ["description", "recommended_body", "experience_venue"]:
            if name in self.fields:
                self.fields[name].widget = forms.Textarea(attrs={"rows": 3})

        for name in ["cover_image", "menu_pdf"]:
            if name in self.fields:
                self.fields[name].widget = forms.ClearableFileInput()

        for name in ["website", "reservation_url", "instagram", "menu_qr_url"]:
            if name in self.fields:
                self.fields[name].widget = forms.URLInput()

        if "min_age" in self.fields:
            self.fields["min_age"].widget = forms.NumberInput(attrs={"min": 0, "step": 1})

        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                css = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = (css + " form-select rounded-3").strip()

        for name, field in self.fields.items():
            if not isinstance(field.widget, (forms.Select, forms.SelectMultiple, forms.ClearableFileInput)):
                css = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = (css + " form-control rounded-3").strip()

        placeholders = {
            "name": "Nombre del local",
            "min_age": "18+",
            "dress_code": "Smart casual",
            "hours_short": "Vie–Sáb 21:00–04:00",
            "address": "Dirección",
            "phone": "+56 9 ...",
            "website": "https://tu-sitio.cl",
            "instagram": "https://instagram.com/tu_local",
            "reservation_url": "https://pasarela/…",
            "experience_venue": "Ej: Clásicos bien hechos & signature drinks",
            "highlights_1": "Ej: Mocktails",
            "highlights_2": "Ej: Negroni",
            "highlights_3": "Ej: Gin tonic",
            "vgt_promos_1": "Ej: 2x1 hasta las 23:00",
            "vgt_promos_2": "Ej: Barra libre 00:00–01:00",
            "vgt_promos_3": "Ej: Ladies Night",
        }
        for n, ph in placeholders.items():
            if n in self.fields:
                self.fields[n].widget.attrs["placeholder"] = ph

        if "experience_venue" in self.fields:
            self.fields["experience_venue"].widget.attrs.setdefault("maxlength", 120)

        if "vibe_tags" in self.fields:
            self.fields["vibe_tags"].required = False
            css = self.fields["vibe_tags"].widget.attrs.get("class", "")
            self.fields["vibe_tags"].widget.attrs["class"] = (css + " d-none").strip()
            self.fields["vibe_tags"].widget.attrs["disabled"] = "disabled"

    def clean_experience_venue(self):
        txt = self.cleaned_data.get("experience_venue", "")
        return txt.strip()




class EventForm(ModelForm):
    class Meta:
        model = Event
        fields = [
            "title","category","start_at","end_at","flyer_image","eyebrow_text",
            "badge_text","external_ticket_url","is_featured","feature_order","is_published",
        ]
        labels = {
            "title": "Título del evento","slug": "Slug (URL)","category": "Categoría","Commune": "Comuna",   # o "commune": "Comuna"
            "flyer_image": "Flyer (imagen)", "eyebrow_text": "Texto superior corto (ej: “Viernes · 22:00”)",
            "badge_text": "Badge (ej: “Preventa”, “2x1”)","external_ticket_url": "URL de compra/entradas",
            "is_featured": "Destacado en hero","feature_order": "Orden del destacado","is_published": "Publicado",
        }
        help_texts = {
            "slug": "Si lo dejas vacío, se generará automáticamente.",
            "feature_order": "N° menor = aparece antes en la grilla de destacados.",
        }
        widgets = {
            # usa <input type="datetime-local"> (recuerda convertir zona horaria en la vista si aplica)
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-control", "maxlength": 180, "placeholder": "Ej: DJ Nova · Noche electrónica"}),
            "flyer_image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "eyebrow_text": forms.TextInput(attrs={"class": "form-control", "maxlength": 60, "placeholder": "Viernes · 22:00"}),
            "badge_text": forms.TextInput(attrs={"class": "form-control", "maxlength": 60, "placeholder": "Preventa"}),
            "external_ticket_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
            "feature_order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Ajuste visual: checkboxes con form-check
        for name in ["is_featured", "is_published"]:
            self.fields[name].widget.attrs.setdefault("class", "form-check-input")



    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_at")
        end = cleaned.get("end_at")
        if start and end and end <= start:
            self.add_error("end_at", "La fecha/hora de término debe ser posterior al inicio.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)

        # Autogenerar slug si viene vacío
        if not obj.slug:
            # puedes enriquecer con comuna y fecha para asegurar unicidad legible
            parts = [obj.title]
            if getattr(obj, "Commune", None) and getattr(obj.Commune, "name", ""):
                parts.append(obj.Commune.name)
            if obj.start_at:
                parts.append(obj.start_at.strftime("%Y%m%d"))
            obj.slug = slugify("-".join(parts))[:210]

        if commit:
            obj.save()
            self.save_m2m()
        return obj

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class VenueGalleryUploadForm(forms.Form):
    images = forms.FileField(
        widget=MultipleFileInput(attrs={"multiple": True, "class": "form-control"}),
        required=True
    )
    caption = forms.CharField(
        max_length=160, required=False,
        widget=forms.TextInput(attrs={"class":"form-control"})
    )
    
class VenueCreateForm(LabelsMixin, ModelForm):
    class Meta:
        model = Venue
        fields = [
            "name", "Commune", "category",
            "address", "phone",
            "description", "cover_image",
            # agrega otros campos básicos si quieres
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "class": "form-control rounded-3"}),
            "cover_image": forms.ClearableFileInput(attrs={"class": "form-control rounded-3"}),
            "category": forms.Select(attrs={"class": "form-select rounded-3"}),
            "name": forms.TextInput(attrs={"class": "form-control rounded-3", "placeholder": "Ej: Club Midnight"}),
            "address": forms.TextInput(attrs={"class": "form-control rounded-3", "placeholder": "Av. del Mar 1234"}),
            "phone": forms.TextInput(attrs={"class": "form-control rounded-3", "placeholder": "+56 9 ..."}),
            "Commune": forms.Select(attrs={"class": "form-select rounded-3 d-none"}),  # la ocultamos (se sincroniza por JS)
        }