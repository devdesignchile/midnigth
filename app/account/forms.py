# app/accounts/forms.py
from datetime import date
from django.contrib.auth.models import User
from django.utils.text import slugify
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Profile, OwnerProfile, GuestProfile
from app.places.models import Venue, Commune

PUBLIC_DOMAINS = {
    "gmail.com","outlook.com","hotmail.com","yahoo.com","icloud.com",
    "live.com","proton.me","protonmail.com"
}

def _unique_slug(model, base: str, field_name: str = "slug") -> str:
    """Genera un slug único dentro de `model` sin tocar el modelo."""
    base = slugify(base) or "venue"
    slug = base
    i = 2
    exists = model.objects.filter(**{field_name: slug}).exists()
    while exists:
        slug = f"{base}-{i}"
        i += 1
        exists = model.objects.filter(**{field_name: slug}).exists()
    return slug

# ========== Dueño de local ==========
class OwnerSignupForm(forms.Form):
    venue_name = forms.CharField(
        label="Nombre del local", max_length=120,
        widget=forms.TextInput(attrs={
            "class": "form-control rounded-3",
            "placeholder": "Ej: OVO",
            "autocomplete": "organization"
        })
    )
    admin_name = forms.CharField(
        label="Nombre administrador", max_length=120,
        widget=forms.TextInput(attrs={
            "class": "form-control rounded-3",
            "placeholder": "Nombre y apellido",
            "autocomplete": "name"
        })
    )
    rut_comercio = forms.CharField(
        label="RUT comercio", max_length=14, help_text="Formato 12.345.678-5",
        widget=forms.TextInput(attrs={
            "class": "form-control rounded-3",
            "placeholder": "12.345.678-5",
            "inputmode": "text",
            "autocomplete": "off"
        })
    )
    company_email = forms.EmailField(
        label="Correo corporativo",
        widget=forms.EmailInput(attrs={
            "class": "form-control rounded-3",
            "placeholder": "tu@midnightrm.cl",
            "autocomplete": "email"
        })
    )
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control rounded-3",
            "placeholder": "••••••",
            "autocomplete": "new-password"
        })
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control rounded-3",
            "placeholder": "••••••",
            "autocomplete": "new-password"
        })
    )

    # --- Validaciones ---
    def clean_company_email(self):
        email = self.cleaned_data["company_email"].strip().lower()
        parts = email.split("@", 1)
        if len(parts) != 2 or not parts[1]:
            raise ValidationError("Correo inválido.")
        dom = parts[1]

        # MVP: bloquear dominios públicos
        if dom in PUBLIC_DOMAINS:
            raise ValidationError("Solo se acepta dominio corporativo.")

        # Unicidad básica
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Este email ya está registrado para acceso.")
        if OwnerProfile.objects.filter(company_email__iexact=email).exists():
            raise ValidationError("Este correo corporativo ya está asociado a otro local.")

        self.cleaned_data["company_domain"] = dom
        return email

    def clean(self):
        c = super().clean()
        if c.get("password1") != c.get("password2"):
            self.add_error("password2", "Las contraseñas no coinciden.")
        return c

    # --- Guardado ---
    @transaction.atomic
    def save(self):
        c = self.cleaned_data

        # 1) User + Profile + OwnerProfile
        base = slugify(c["venue_name"]) or c["company_email"].split("@")[0]
        username = base
        i = 1
        while User.objects.filter(username=username).exists():
            i += 1
            username = f"{base}{i}"

        user = User.objects.create_user(
            username=username,
            email=c["company_email"],
            password=c["password1"],
            first_name=c["admin_name"],
        )
        profile = Profile.objects.create(user=user, role="owner")
        owner = OwnerProfile.objects.create(
            profile=profile,
            venue_name=c["venue_name"],
            admin_name=c["admin_name"],
            rut_comercio=c["rut_comercio"],
            company_email=c["company_email"],
            company_domain=c["company_domain"],
        )

        # 2) Venue borrador automático (sin tocar modelos)
        slug_val = _unique_slug(Venue, c["venue_name"])
        venue_kwargs = {
            "name": c["venue_name"],
            "slug": slug_val,
            "category": "other",     # valor seguro por defecto
            "owner_user": user,      # dueño
            "is_published": False,   # primero edita, luego publica
        }

        # Commune: intenta “Santiago” o la primera disponible
        commune = Commune.objects.filter(name__iexact="Santiago").first() or Commune.objects.first()
        if commune:
            # nombre canónico
            try:
                venue_kwargs["commune"] = commune
                Venue.objects.create(**venue_kwargs)
            except TypeError:
                # soporte si tu campo se llama literalmente "Commune"
                venue_kwargs.pop("commune", None)
                venue_kwargs["Commune"] = commune
                Venue.objects.create(**venue_kwargs)
        else:
            # si Commune es obligatorio y no hay registros, esto fallará y revertirá la transacción
            Venue.objects.create(**venue_kwargs)

        return user


# ========== Invitado / Asistente ==========
class GuestSignupForm(forms.Form):
    first_name = forms.CharField(
        label="Nombre", max_length=80,
        widget=forms.TextInput(attrs={
            "class": "form-control rounded-3",
            "placeholder": "Nombre",
            "autocomplete": "given-name"
        })
    )
    last_name = forms.CharField(
        label="Apellido", max_length=80,
        widget=forms.TextInput(attrs={
            "class": "form-control rounded-3",
            "placeholder": "Apellido",
            "autocomplete": "family-name"
        })
    )
    # MISMO PATRÓN QUE EN DoctorForm (format + input_formats)
    birth_date = forms.DateField(
        label="Fecha de nacimiento",
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control rounded-3"},
            format="%Y-%m-%d",
        ),
        input_formats=["%Y-%m-%d"],
        required=True,
    )
    email = forms.EmailField(
        label="Correo",
        widget=forms.EmailInput(attrs={
            "class": "form-control rounded-3",
            "placeholder": "tucorreo@ejemplo.com",
            "autocomplete": "email"
        })
    )
    city = forms.ModelChoiceField(
        label="Comuna",
        queryset=Commune.objects.none(),  # se definirá en __init__ para permitir filtrados dinámicos
        empty_label="Selecciona una comuna",
        widget=forms.Select(attrs={
            "class": "form-select rounded-3 bg-white text-dark",
            "autocomplete": "address-level2"
        })
    )
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control rounded-3 ",
            "placeholder": "••••••",
            "autocomplete": "new-password"
        })
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control rounded-3",
            "placeholder": "••••••",
            "autocomplete": "new-password"
        })
    )

    def clean_birth_date(self):
        bd = self.cleaned_data["birth_date"]
        today = date.today()
        age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        if age < 18:
            raise forms.ValidationError("Debes ser mayor de 18 años.")
        return bd

    def clean(self):
        c = super().clean()
        if c.get("password1") != c.get("password2"):
            self.add_error("password2", "Las contraseñas no coinciden.")
        return c

    def save(self):
        c = self.cleaned_data
        base = slugify(f'{c["first_name"]}-{c["last_name"]}') or c["email"].split("@")[0]
        username = base
        i = 1
        while User.objects.filter(username=username).exists():
            i += 1
            username = f"{base}{i}"

        user = User.objects.create_user(
            username=username,
            email=c["email"],
            password=c["password1"],
            first_name=c["first_name"],
            last_name=c["last_name"],
        )
        profile = Profile.objects.create(user=user, role="guest")

        selected_commune = c["city"]        # instancia Commune
        GuestProfile.objects.create(
            profile=profile,
            first_name=c["first_name"],
            last_name=c["last_name"],
            birth_date=c["birth_date"],
            city=selected_commune.name,      # <-- IMPORTANTE: guardar string
        )
        return user

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Este email ya está registrado.")
        return email


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Correo",
        widget=forms.EmailInput(attrs={
            "class": "form-control form-control-lg bg-black text-white border-0 rounded-pill px-4",
            "placeholder": "correo@empresa.com",
            "autocomplete": "email",
        })
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control form-control-lg bg-black text-white border-0 rounded-pill px-4",
            "placeholder": "••••••••",
            "autocomplete": "current-password",
            "id": "passwordField",
        })
    )
    remember = forms.BooleanField(
        label="Recordarme",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )

from django import forms

class VenueForm(forms.ModelForm):
    class Meta:
        model = Venue
        fields = [
            "name", "category", "cover_image", "description",
            "hours_short", "min_age", "dress_code",
            "payment_methods",
            "recommended_title", "recommended_body",
            "menu_pdf", "menu_qr_url",
            "vgt_promos_1", "vgt_promos_2", "vgt_promos_3",
            "website", "instagram", "reservation_url",
            "address", "phone",
            "vibe_tags",
            "is_published",
        ]


