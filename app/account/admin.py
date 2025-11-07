# app/account/admin.py
from django.contrib import admin
from django.utils import timezone
from .models import Profile, OwnerProfile, GuestProfile, Subscription
from django.urls import reverse
from django.utils.html import format_html
from datetime import timedelta
# ---------------- Inlines ----------------
class OwnerProfileInline(admin.StackedInline):
    model = OwnerProfile
    fk_name = "profile"
    extra = 0
    can_delete = True
    verbose_name = "Dueño de local"
    verbose_name_plural = "Dueño de local"


class GuestProfileInline(admin.StackedInline):
    model = GuestProfile
    fk_name = "profile"
    extra = 0
    can_delete = True
    verbose_name = "Asistente"
    verbose_name_plural = "Asistente"


# ---------------- Profile ----------------
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user_username", "user_email", "role", "sub_status", "sub_until")
    search_fields = ("user__username", "user__email")
    list_filter = ("role",)
    inlines = [OwnerProfileInline, GuestProfileInline]

    @admin.display(ordering="user__username", description="Usuario")
    def user_username(self, obj):
        return getattr(obj.user, "username", "")

    @admin.display(ordering="user__email", description="Email")
    def user_email(self, obj):
        return getattr(obj.user, "email", "")

    @admin.display(description="Sub.")
    def sub_status(self, obj):
        sub = getattr(obj.user, "subscription", None)
        return getattr(sub, "status", "—")

    @admin.display(description="Válida hasta")
    def sub_until(self, obj):
        sub = getattr(obj.user, "subscription", None)
        dt = getattr(sub, "current_period_end", None)
        return timezone.localtime(dt).strftime("%Y-%m-%d %H:%M") if dt else "—"


# --------- Filtro por suscripción ----------
class SubscriptionStatusFilter(admin.SimpleListFilter):
    title = "Estado de suscripción"
    parameter_name = "sub_status"

    def lookups(self, request, model_admin):
        return [
            ("ACTIVE", "Activa"),
            ("PAUSED", "Pausada"),
            ("CANCELLED", "Cancelada"),
            ("NONE", "Sin suscripción"),
        ]

    def queryset(self, request, queryset):
        val = self.value()
        if not val:
            return queryset
        if val == "NONE":
            return queryset.filter(profile__user__subscription__isnull=True)
        return queryset.filter(profile__user__subscription__status=val)


# ---------------- OwnerProfile ----------------
@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_username",
        "venue_name",
        "admin_name",
        "rut_comercio",
        "company_email",
        "company_domain",
        "owner_verified",
        "is_subscribed_admin",  # ✅ ahora sí es campo real
        "sub_until",
    )
    list_editable = ("is_subscribed_admin",)  # ✅ ya no da error
    search_fields = (
        "venue_name",
        "admin_name",
        "rut_comercio",
        "company_email",
        "company_domain",
        "profile__user__username",
        "profile__user__email",
    )
    list_filter = ("owner_verified", "company_domain", SubscriptionStatusFilter)

    # --- columnas ---
    @admin.display(ordering="profile__user__username", description="Usuario")
    def user_username(self, obj):
        return getattr(obj.profile.user, "username", "")

    @admin.display(description="Suscrito", boolean=True)
    def is_subscribed_admin(self, obj):
        """
        Muestra si el usuario tiene una suscripción activa o forzada.
        Este campo será editable en el admin como un checkbox.
        """
        sub = getattr(obj.profile.user, "subscription", None)
        if not sub:
            return False
        return sub.is_active()

    @admin.display(description="Válida hasta")
    def sub_until(self, obj):
        sub = getattr(obj.profile.user, "subscription", None)
        dt = getattr(sub, "current_period_end", None)
        return timezone.localtime(dt).strftime("%Y-%m-%d %H:%M") if dt else "—"

    # --- Guardado automático del checkbox ---
    def save_model(self, request, obj, form, change):
        """
        Al marcar/desmarcar 'is_subscribed_admin' desde el admin, 
        crea o actualiza la suscripción correspondiente.
        """
        super().save_model(request, obj, form, change)
        user = getattr(obj.profile, "user", None)
        if not user:
            return

        is_subscribed = form.cleaned_data.get("is_subscribed_admin", False)
        sub, _ = Subscription.objects.get_or_create(user=user)

        if is_subscribed:
            sub.override_status = Subscription.ACTIVE
            sub.override_until = timezone.now() + timezone.timedelta(days=30)
            sub.override_reason = "Activado manualmente desde admin"
        else:
            sub.override_status = None
            sub.override_until = None
            sub.override_reason = "Desactivado manualmente desde admin"

        sub.save()


# ---------------- GuestProfile ----------------
@admin.register(GuestProfile)
class GuestProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_username",
        "first_name",
        "last_name",
        "city",
        "age_display",
        "age_band_display",
        "created_at",
    )
    search_fields = (
        "first_name",
        "last_name",
        "city",
        "profile__user__username",
        "profile__user__email",
    )
    list_filter = ("city",)

    @admin.display(ordering="profile__user__username", description="Usuario")
    def user_username(self, obj):
        return getattr(obj.profile.user, "username", "")

    @admin.display(description="Edad")
    def age_display(self, obj):
        return obj.age

    @admin.display(description="Rango etario")
    def age_band_display(self, obj):
        return obj.age_band

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    # Trae user → profile → owner en una sola query
    list_select_related = ("user", "user__profile", "user__profile__owner")

    list_display = (
        "id",
        "user",                      # username del usuario
        "owner_link",               # link al OwnerProfile
        "owner_venue",              # Nombre del local
        "owner_admin_name",         # Admin del local
        "owner_company_email",      # Correo corporativo
        "owner_domain",             # Dominio comercial
        "owner_verified_badge",     # ✓ / ✗
        "effective_status",         # ¿Efectiva?
        "status",                   # Estado MP
        "current_period_end",
        "override_status",
        "override_until",
        "override_reason",
    )

    # Búsqueda también por campos del owner
    search_fields = (
        "user__username", "user__email", "mp_preapproval_id",
        "user__profile__owner__venue_name",
        "user__profile__owner__admin_name",
        "user__profile__owner__company_email",
        "user__profile__owner__company_domain",
    )

    # Filtros incluyendo owner_verified
    list_filter = (
        "status", "override_status",
        ("user__profile__owner__owner_verified", admin.BooleanFieldListFilter),
        "user__profile__owner__company_domain",
    )

    list_editable = ("override_status", "override_until", "override_reason")

    fieldsets = (
        ("Origen Mercado Pago", {
            "fields": ("user", "mp_preapproval_id", "status", "current_period_end"),
        }),
        ("Override manual (admin)", {
            "fields": ("override_status", "override_until", "override_reason"),
            "description": "Si defines ACTIVA + fecha, el owner queda activo aunque MP esté inactivo."
        }),
        ("Metadatos", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    readonly_fields = ("created_at", "updated_at")

    # ------- Columnas de Owner (con fallback seguro) -------
    def _owner(self, obj):
        return getattr(getattr(obj.user, "profile", None), "owner", None)

    @admin.display(description="Owner", ordering="user__profile__owner__venue_name")
    def owner_link(self, obj):
        owner = self._owner(obj)
        if not owner:
            return "—"
        url = reverse("admin:account_ownerprofile_change", args=[owner.id])
        return format_html('<a href="{}">{}</a>', url, owner.venue_name or f"Owner #{owner.id}")

    @admin.display(description="Nombre del local", ordering="user__profile__owner__venue_name")
    def owner_venue(self, obj):
        owner = self._owner(obj)
        return getattr(owner, "venue_name", "—") if owner else "—"

    @admin.display(description="Nombre administrador", ordering="user__profile__owner__admin_name")
    def owner_admin_name(self, obj):
        owner = self._owner(obj)
        return getattr(owner, "admin_name", "—") if owner else "—"

    @admin.display(description="Correo corporativo", ordering="user__profile__owner__company_email")
    def owner_company_email(self, obj):
        owner = self._owner(obj)
        return getattr(owner, "company_email", "—") if owner else "—"

    @admin.display(description="Dominio comercial", ordering="user__profile__owner__company_domain")
    def owner_domain(self, obj):
        owner = self._owner(obj)
        return getattr(owner, "company_domain", "—") if owner else "—"

    @admin.display(description="Owner verified", boolean=True)
    def owner_verified_badge(self, obj):
        owner = self._owner(obj)
        return bool(getattr(owner, "owner_verified", False)) if owner else False

    # ------- Estado efectivo -------
    @admin.display(description="¿Efectiva?")
    def effective_status(self, obj):
        return "Activa" if obj.is_active() else "No activa"

    # ------- Normalización al guardar (list_editable y form) -------
    def save_model(self, request, obj, form, change):
        """
        Reglas de sincronización:
        - override = ACTIVA   -> status ACTIVA; asegura fechas (>= ahora+30d si faltan).
        - override = PAUSADA/None -> limpia override; si no queda activa por MP -> status PAUSADA y corta periodo.
        - override = CANCELADA -> limpia override; status CANCELADA y corta periodo.
        """
        super().save_model(request, obj, form, change)

        now = timezone.now()
        end_30d = now + timedelta(days=30)

        if obj.override_status == Subscription.ACTIVE:
            if not obj.override_until or obj.override_until < now:
                obj.override_until = end_30d
            obj.status = Subscription.ACTIVE
            if not obj.current_period_end or obj.current_period_end < obj.override_until:
                obj.current_period_end = obj.override_until
            obj.save()

        elif obj.override_status == Subscription.CANCELLED:
            obj.override_until = None
            obj.override_reason = (obj.override_reason or "Cancelada manualmente").strip()
            obj.status = Subscription.CANCELLED
            obj.current_period_end = now
            obj.save()

        else:
            obj.override_status = None
            obj.override_until = None
            obj.override_reason = (obj.override_reason or "").strip()
            obj.save()
            if not obj.is_active():
                obj.status = Subscription.PAUSED
                obj.current_period_end = now
                obj.save()

    # ------- Acciones rápidas opcionales -------
    actions = ["dar_cortesia_30d", "pausar_override", "quitar_override"]

    @admin.action(description="Dar cortesía 30 días (override ACTIVA)")
    def dar_cortesia_30d(self, request, queryset):
        now = timezone.now()
        count = 0
        for s in queryset:
            s.override_status = Subscription.ACTIVE
            s.override_until = now + timedelta(days=30)
            s.override_reason = "Cortesía 30d"
            s.status = Subscription.ACTIVE
            if not s.current_period_end or s.current_period_end < s.override_until:
                s.current_period_end = s.override_until
            s.save()
            count += 1
        self.message_user(request, f"{count} suscripción(es) activadas por cortesía 30 días.")

    @admin.action(description="Pausar override (sin borrar MP)")
    def pausar_override(self, request, queryset):
        now = timezone.now()
        count = 0
        for s in queryset:
            s.override_status = Subscription.PAUSED
            s.override_until = None
            s.save()
            if not s.is_active():
                s.status = Subscription.PAUSED
                s.current_period_end = now
                s.save()
            count += 1
        self.message_user(request, f"{count} suscripción(es) con override pausado.")

    @admin.action(description="Quitar override")
    def quitar_override(self, request, queryset):
        now = timezone.now()
        count = 0
        for s in queryset:
            s.override_status = None
            s.override_until = None
            s.override_reason = ""
            s.save()
            if not s.is_active():
                s.status = Subscription.PAUSED
                s.current_period_end = now
                s.save()
            count += 1
        self.message_user(request, f"Override removido en {count} suscripción(es).")
