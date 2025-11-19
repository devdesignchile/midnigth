# ===== Standard library =====
import json
import re
from functools import reduce
from operator import and_
from urllib.parse import urlparse
from datetime import datetime, timedelta, time

# ===== Third-party =====
import mercadopago

# ===== Django =====
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models import (
    Q, F, Count, Case, When, Value, IntegerField
)
from django.http import (
    JsonResponse, Http404, HttpResponseBadRequest, HttpResponseNotAllowed, QueryDict
)
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import (
    TemplateView, DetailView, UpdateView, ListView, DeleteView, CreateView
)
from django.views.generic.edit import FormMixin

# ===== Local apps =====
from app.account.models import Subscription, OwnerProfile
from app.places.models import Venue, Event, Commune, Tag, Photo
from app.places.forms import (
    VenueCreateForm, VenueForm, VenueUpdateForm, EventForm, VenueGalleryUploadForm
)

# y tu modelo


from .models import Venue, Commune, Event # ajusta import según tu app
class HomeView(TemplateView):
    template_name = "index.html"

    # =============================
    # --- Métodos auxiliares ---
    # =============================

    def _commune_from_string(self, value: str):
        if not value:
            return None
        value = value.strip()
        return Commune.objects.filter(
            Q(slug__iexact=value) | Q(name__iexact=value)
        ).first()

    def _get_default_commune(self):
        """Ciudad por defecto: Santiago."""
        c = Commune.objects.filter(slug__iexact="santiago").first()
        if c: return c
        c = Commune.objects.filter(name__iexact="Santiago").first()
        if c: return c
        return Commune.objects.order_by("name").first()

    def _commune_from_user(self, request):
        """Detecta comuna según el perfil del usuario."""
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None

        profile = getattr(user, "profile", None)
        if not profile:
            return None

        # Invitado
        if getattr(profile, "is_guest", False):
            guest = getattr(profile, "guest", None)
            city_str = getattr(guest, "city", "") if guest else ""
            c = self._commune_from_string(city_str)
            if c:
                return c

        # Owner
        if getattr(profile, "is_owner", False):
            owner_venues = Venue.objects.select_related("Commune").filter(owner_user=user)
            if owner_venues.exists():
                return owner_venues.first().Commune

        return None

    def _get_city(self, request):
        """Orden de resolución:
        1️⃣ ?city= (slug o nombre)
        2️⃣ Usuario autenticado (guest u owner)
        3️⃣ Fallback: Santiago (predeterminada para visitantes no registrados)
        """
        city_raw = (request.GET.get("city") or "").strip()
        if city_raw:
            c = self._commune_from_string(city_raw)
            if c:
                return c

        # Usuario logueado (guest u owner)
        c = self._commune_from_user(request)
        if c:
            return c

        # Fallback global (visitantes anónimos)
        return self._get_default_commune()

    @staticmethod
    def _is_http_url(u: str) -> bool:
        try:
            p = urlparse(u or "")
            return p.scheme in ("http", "https") and bool(p.netloc)
        except Exception:
            return False

    # =============================
    # --- Contexto principal ---
    # =============================
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        city = self._get_city(self.request)

        # Ciudad activa (siempre hay una: por defecto Santiago)
        ctx["city"] = city
        ctx["active_city_label"] = city.name if city else "Chile"
        ctx["active_city"] = city.slug if city else ""

        # ====================================================
        # 1️⃣ TRENDING — Eventos próximos (48h)
        # ====================================================
        trending_items = []
        if city:
            now = timezone.now()
            window_end = now + timedelta(days=7)  # antes: timedelta(hours=48)

            events_qs = (
                Event.objects
                .filter(
                    Commune=city,
                    start_at__gte=now,
                    start_at__lte=window_end
                )
                .select_related("venue")
                .order_by("start_at")      # ya no lo limito a [:4] aquí
            )

            for e in events_qs:
                ext = getattr(e, "external_ticket_url", "") or ""
                href = ext if self._is_http_url(ext) else ""
                if not href and e.venue:
                    href = reverse("venue-detail", kwargs={"slug": e.venue.slug})
                if not href:
                    # si no tengo a dónde mandar al usuario, salto el evento
                    continue

                img = (
                    e.flyer_image.url if getattr(e, "flyer_image", None) else
                    (e.venue.cover_image.url if (e.venue and getattr(e.venue, "cover_image", None)) else "")
                )

                trending_items.append({
                    "type": "evento",
                    "title": e.title,
                    "time": timezone.localtime(e.start_at).strftime("%a %H:%M"),
                    "venue": e.venue.name if e.venue else city.name,
                    "href": href,
                    "external": bool(self._is_http_url(ext)),
                    "badge": e.badge_text or "Próximo",
                    "badgeVariant": "primary",
                    "img": img,
                    "tags": getattr(e, "tags_list", []),
                })
                
                ctx["trending_items"] = trending_items[:8]  # limitar a 8

        # ====================================================
        # 2️⃣ VENUES DESTACADOS
        # ====================================================
        featured_qs = Venue.objects.select_related("Commune").filter(
            Commune=city,
            
        )

        ordering = []
        if hasattr(Venue, "is_advertised"):
            ordering.append("-is_advertised")
        if hasattr(Venue, "is_featured"):
            ordering.append("-is_featured")
        ordering.append("name")

        ctx["featured_venues"] = featured_qs.order_by(*ordering)[:3]

        # ====================================================
        # 3️⃣ OFERTAS — Promos visibles
        # ====================================================
        offers_items = []
        venues_with_promos = (
            Venue.objects
            .select_related("Commune")
            .filter(Commune=city)
            .only(
                "slug", "name", "address", "Commune",
                "cover_image", "gallery_venue",
                "vgt_promos_1", "vgt_promos_2", "vgt_promos_3",
            )
        )

        def build_offer_item(v, promo_text):
            if not promo_text:
                return None
            img = (
                v.cover_image.url if getattr(v, "cover_image", None) else
                (v.gallery_venue.url if getattr(v, "gallery_venue", None) else "")
            )
            return {
                "href": reverse("venue-detail", kwargs={"slug": v.slug}),
                "title": v.name,
                "subtitle": v.Commune.name,
                "badge": promo_text,
                "img": img,
                "address": v.address or "",
            }

        for v in venues_with_promos:
            for promo_field in ["vgt_promos_1", "vgt_promos_2", "vgt_promos_3"]:
                promo_text = getattr(v, promo_field, None)
                if promo_text:
                    item = build_offer_item(v, promo_text)
                    if item:
                        offers_items.append(item)

        ctx["offers_items"] = offers_items[:6]

        # ====================================================
        # 4️⃣ MINI MAPA — Solo comuna activa
        # ====================================================
        mini_qs = Venue.objects.select_related("Commune")
        if city:
            mini_qs = mini_qs.filter(Commune=city)

        def _lat(v):
            for f in ("lat", "latitude", "geo_lat"):
                if hasattr(v, f) and getattr(v, f) not in (None, ""):
                    return float(getattr(v, f))
            return None

        def _lng(v):
            for f in ("lon", "lng", "longitude", "geo_lng"):
                if hasattr(v, f) and getattr(v, f) not in (None, ""):
                    return float(getattr(v, f))
            return None

        mini_map_venues = []
        for v in mini_qs.only("id", "slug", "name", "address", "Commune"):
            mini_map_venues.append({
                "id": v.id,
                "name": v.name,
                "slug": v.slug,
                "address": v.address or "",
                "commune": v.Commune.name if getattr(v, "Commune", None) else "",
                "lat": _lat(v),
                "lng": _lng(v),
                "href": self.request.build_absolute_uri(
                    reverse("venue-detail", kwargs={"slug": v.slug})
                ),
            })

        ctx["mini_map_venues"] = mini_map_venues

        # ====================================================
        # Debug
        # ====================================================
        user = self.request.user
        print(f"[DEBUG] Usuario: {'anon' if not user.is_authenticated else user.username}")
        print(f"[DEBUG] Ciudad activa: {city}")
        print(f"[DEBUG] Eventos 48h: {len(trending_items)}")
        print(f"[DEBUG] Venues destacados: {featured_qs.count()}")
        print(f"[DEBUG] Ofertas: {len(offers_items)}")
        print(f"[DEBUG] Venues para mini-mapa: {len(mini_map_venues)}")

        return ctx


class VenueSearchView(ListView):
    template_name = "search_results.html"
    context_object_name = "venues"
    model = Venue
    paginate_by = 24

    # Campos en los que buscar
    SEARCH_FIELDS = [
        "name__icontains",
        "description__icontains",
        "address__icontains",
        "Commune__name__icontains",
    ]

    def _build_term_q(self, term: str) -> Q:
        """Crea una Q (OR) entre los campos para un término individual."""
        q = Q()
        for f in self.SEARCH_FIELDS:
            q |= Q(**{f: term})
        return q

    def get_queryset(self):
        """Filtra los venues según el término de búsqueda."""
        raw_q = (self.request.GET.get("q") or "").strip()
        qs = Venue.objects.select_related("Commune").all()  # 👈 quitamos el filtro is_published=True

        if not raw_q:
            return qs.order_by("name")

        # Divide la búsqueda en palabras separadas por espacios
        terms = [t for t in re.split(r"\s+", raw_q) if t]

        # Aplica un AND entre términos (cada palabra debe calzar en al menos un campo)
        term_qs = [self._build_term_q(t) for t in terms]
        if term_qs:
            qs = qs.filter(reduce(and_, term_qs))

        return qs.order_by("name")

    def get_context_data(self, **kwargs):
        """Agrega el término buscado y el total de resultados al contexto."""
        ctx = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q") or "").strip()
        ctx["q"] = q
        ctx["total"] = self.get_queryset().count()
        return ctx

class MyVenuesListView(ListView, LoginRequiredMixin):
    template_name = "owner_venues.html"
    context_object_name = "venues"
    paginate_by = 10

    def get_queryset(self):
        return (
            Venue.objects
            .filter(owner_user=self.request.user)
            .select_related("Commune")            # opcional: performance
            .prefetch_related("vibe_tags", "photos")  # opcional
            .order_by("-id", "name")              # <- aquí el fix
        )

class VenueDetailView(FormMixin, DetailView):
    model = Venue
    slug_field = "slug"
    slug_url_kwarg = "slug"
    template_name = "venue_detail.html"
    context_object_name = "venue"
    form_class = VenueUpdateForm                      # 👈 este es el form que editas en el modal

    def get_queryset(self):
        return (
            Venue.objects
            .select_related("Commune", "owner_user")
            .prefetch_related("vibe_tags", "photos")
        )

    def is_owner(self):
        obj = self.get_object()
        return (
            self.request.user.is_authenticated
            and obj.owner_user_id == self.request.user.id
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        v = ctx["venue"]
        now = timezone.now()

        # Próximos: primero futuros; luego pasados cercanos
        ctx["upcoming_events"] = (
            Event.objects
            .filter(venue=v)
            .exclude(start_at__isnull=True)
            .annotate(
                is_past=Case(
                    When(start_at__lt=now, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
            .order_by("is_past", "start_at")[:12]
        )

        # Carrusel: solo futuros
        ctx["carousel_events"] = (
            Event.objects
            .filter( venue=v, start_at__gte=now)  #is_published=True para despues
            .order_by("start_at")[:10]
        )

        # Galería
        ctx["gallery"] = v.photos.all().order_by("sort_order", "pk")[:12]
        ctx["is_owner"] = self.is_owner()

        # Tags para chips
        ctx["all_tags"] = Tag.objects.order_by("name")
        if self.request.method == "POST":
            # Si hubo error de validación, conserva lo que el usuario marcó
            try:
                ctx["selected_tag_ids"] = [int(x) for x in self.request.POST.getlist("vibe_tags")]
            except ValueError:
                ctx["selected_tag_ids"] = []
        else:
            ctx["selected_tag_ids"] = list(v.vibe_tags.values_list("id", flat=True))

        if ctx["is_owner"]:
            # Form del modal (edición inline)
            ctx["form"] = self.get_form()

            # Subida múltiple de fotos
            ctx["gallery_form"] = VenueGalleryUploadForm()
            ctx["upload_url"] = reverse("venue-gallery-upload", kwargs={"slug": v.slug})

        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.is_owner():
            messages.error(request, "No tienes permisos para editar este lugar.")
            return redirect(self.object.get_absolute_url())

        form = self.get_form()
        if form.is_valid():
            # commit=True => guarda M2M también con ModelForm
            form.save()
            messages.success(request, "Cambios guardados.")
            return redirect(self.object.get_absolute_url())

        # Re-render con errores y reabrir el modal
        context = self.get_context_data(object=self.object)
        context["owner_form"] = form
        context["open_modal"] = True
        return self.render_to_response(context)

class VenueUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Venue
    form_class = VenueUpdateForm
    slug_field = "slug"
    slug_url_kwarg = "slug"
    template_name = "venue_update_form.html"
    context_object_name = "venue"

    def get_queryset(self):
        qs = (
            Venue.objects
            .select_related("Commune", "owner_user")
            .prefetch_related("vibe_tags")
        )
        u = self.request.user
        return qs if (u.is_superuser or u.is_staff) else qs.filter(owner_user=u)

    def test_func(self):
        obj = self.get_object()
        u = self.request.user
        return u.is_authenticated and (obj.owner_user_id == u.id or u.is_staff or u.is_superuser)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("No tienes permiso para editar este local.")
        return super().handle_no_permission()

    # ---- Contexto extra para los chips de tags ----
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        v = self.object

        ctx["all_tags"] = Tag.objects.order_by("name")

        # Si venimos de POST con errores, conserva lo que el usuario marcó
        if self.request.method == "POST":
            try:
                ctx["selected_tag_ids"] = [int(x) for x in self.request.POST.getlist("vibe_tags")]
            except ValueError:
                ctx["selected_tag_ids"] = []
        else:
            ctx["selected_tag_ids"] = list(v.vibe_tags.values_list("id", flat=True))

        return ctx

    def form_valid(self, form):
        # Guarda incluyendo M2M
        obj = form.save(commit=True)
        messages.success(self.request, "¡Ficha del local actualizada!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("venue-detail", kwargs={"slug": self.object.slug})

class CreateVenueBranchView(LoginRequiredMixin, CreateView):
    model = Venue
    form_class = VenueForm
    slug_field = "slug"
    slug_url_kwarg = "slug"

class EventCreateView(CreateView):
    model = Event
    form_class = EventForm
    template_name = "event_form.html"
    success_url = reverse_lazy("venue-detail")
    template_name = "event_form.html"    
    
    def get_venue(self):
        return get_object_or_404(Venue, slug=self.kwargs["slug"])
    
    def get_success_url(self):
        return reverse("venue-detail", kwargs={"slug": self.kwargs["slug"]})
    
    def test_func(self):
        venue = get_object_or_404(Venue, slug=self.kwargs["slug"])
        u = self.request.user
        return u.is_authenticated and (u.id == venue.owner_user_id or u.is_staff)

    def form_valid(self, form):
        v = self.get_venue()
        form.instance.venue = v
        form.instance.Commune = v.Commune
        return super().form_valid(form)

class EventUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = "event_update_form.html"

    def get_queryset(self):
        # limitar por venue (slug) + luego UpdateView obtiene por pk desde la URL
        return Event.objects.select_related("venue").filter(venue__slug=self.kwargs["slug"])

    def test_func(self):
        obj = self.get_object()
        return (
            getattr(obj, "owner", None) == self.request.user or
            getattr(obj.venue, "owner_user", None) == self.request.user
        )

    def form_valid(self, form):
        messages.success(self.request, "¡Evento actualizado correctamente!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("venue-detail", kwargs={"slug": self.object.venue.slug})

class VenueGalleryUploadView(LoginRequiredMixin, UserPassesTestMixin, View):
    def get_venue(self):
        return get_object_or_404(Venue, slug=self.kwargs["slug"])

    def test_func(self):
        v = self.get_venue()
        u = self.request.user
        return u.is_authenticated and (u.id == v.owner_user_id or u.is_staff)

    def post(self, request, *args, **kwargs):
        venue = self.get_venue()
        files = request.FILES.getlist("images")              # <-- toma múltiples
        caption = (request.POST.get("caption") or "").strip()

        if not files:
            messages.error(request, "Debes seleccionar al menos una imagen.")
            return redirect(reverse("venue-detail", kwargs={"slug": venue.slug}))

        # (Opcional) validaciones básicas por archivo
        for f in files:
            if not getattr(f, "content_type", "").startswith("image/"):
                messages.error(request, f"El archivo «{f.name}» no es una imagen.")
                return redirect(reverse("venue-detail", kwargs={"slug": venue.slug}))
            # if f.size > 8 * 1024 * 1024:  # 8 MB
            #     messages.error(request, f"El archivo «{f.name}» supera 8MB.")
            #     return redirect(reverse("venue-detail", kwargs={"slug": venue.slug}))

        # calcular sort_order incremental
        last = Photo.objects.filter(venue=venue).order_by("-sort_order").first()
        next_order = (last.sort_order + 1) if last else 0

        created = 0
        with transaction.atomic():
            for i, f in enumerate(files):
                p = Photo(venue=venue, caption=caption, sort_order=next_order + i)
                # guardar el archivo físicamente en MEDIA_ROOT
                p.image.save(f.name, f, save=True)
                created += 1

        messages.success(request, f"Se subieron {created} foto(s) a la galería.")
        return redirect(reverse("venue-detail", kwargs={"slug": venue.slug}))
# app/places/views.py  (imports relevantes arriba del archivo)


class CityVenueListView(ListView):
    template_name = "venue_index.html"
    context_object_name = "venues"
    paginate_by = 24
    model = Venue

    # Próxima semana (lunes a domingo)
    def _get_week_range_next_monday_to_sunday(self, tz):
        now = timezone.now().astimezone(tz)
        days_until_next_monday = (7 - now.weekday()) % 7 or 7
        next_monday = (now + timedelta(days=days_until_next_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_end = next_monday + timedelta(days=7)  # exclusivo
        return next_monday, week_end

    def get_queryset(self):
        qs = Venue.objects.select_related("Commune", "owner_user")

        q        = (self.request.GET.get("q") or "").strip()
        cat      = (self.request.GET.get("cat") or "").strip()
        when     = (self.request.GET.get("when") or "cualquier_dia").strip()
        city_raw = (self.request.GET.get("city") or "").strip()

        # 1) Sin ciudad → no listar
        if not city_raw:
            self.needs_city = True
            self.city_input_value = ""
            self.filter_city = None
            return Venue.objects.none()

        # 2) Ciudad por nombre o slug
        slugguess = slugify(city_raw)
        commune = Commune.objects.filter(
            Q(name__iexact=city_raw) | Q(slug__iexact=slugguess)
        ).first()

        if not commune:
            self.needs_city = True
            self.city_input_value = city_raw
            self.filter_city = None
            self.error_city = f"No encontramos la ciudad “{city_raw}”."
            return Venue.objects.none()

        self.needs_city = False
        self.city_input_value = city_raw
        self.filter_city = commune

        # 3) Base: venues por ciudad
        qs = qs.filter(Commune=commune)

        # 4) SOLO dueños con suscripción efectivamente ACTIVA (MP o override)
        #    Usamos la Q reutilizable del modelo para garantizar coherencia.
        now = timezone.now()
        active_owner_user_ids = list(
            Subscription.objects
            .filter(Subscription.active_Q(now))
            .values_list("user_id", flat=True)
        )
        qs = qs.filter(owner_user_id__in=active_owner_user_ids)
        self.active_owner_user_ids = active_owner_user_ids  # lo usamos en el contexto

        # 5) Texto libre
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(description__icontains=q) |
                Q(address__icontains=q)
            )

        # 6) Categoría
        if cat:
            qs = qs.filter(category=cat)

        # 7) Fecha (hoy / esta semana) – filtra por eventos asociados
        tz = timezone.get_current_timezone()
        if when == "hoy":
            today = timezone.localdate()
            start = timezone.make_aware(datetime.combine(today, time.min), tz)
            end   = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min), tz)
            qs = qs.filter(
                events__start_at__gte=start,
                events__start_at__lt=end
            ).distinct()
        elif when == "esta_semana":
            start, end = self._get_week_range_next_monday_to_sunday(tz)
            qs = qs.filter(
                events__start_at__gte=start,
                events__start_at__lt=end
            ).distinct()

        return qs.order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        req = self.request.GET

        city = getattr(self, "filter_city", None)
        ctx["city"] = city

        # Filtros activos
        ctx["q"] = (req.get("q") or "").strip()
        ctx["active_cat"]  = (req.get("cat") or "").strip()
        ctx["active_when"] = (req.get("when") or "").strip()
        ctx["city_input_value"] = getattr(self, "city_input_value", "")

        # Lista de comunas (para datalist/autocomplete)
        cities_qs = Commune.objects.order_by("name")
        ctx["city_names_json"] = json.dumps(
            list(cities_qs.values_list("name", flat=True)),
            ensure_ascii=False
        )

        ctx["needs_city"]   = getattr(self, "needs_city", False)
        ctx["error_city"]   = getattr(self, "error_city", "")
        ctx["venues_count"] = ctx["object_list"].count() if not ctx["needs_city"] else 0

        # Secciones destacadas (también respetan suscripción activa)
        active_ids = getattr(self, "active_owner_user_ids", [])
        if city:
            ctx["featured_venues"] = (
                Venue.objects
                .filter(
                    Commune=city,
                    owner_user_id__in=active_ids
                )
                .order_by("name")[:4]
            )
            ctx["featured_events"] = (
                Event.objects
                .filter(
                    Commune=city,
                    venue__isnull=False,
                    venue__owner_user_id__in=active_ids
                )
                .select_related("venue")
                .order_by("start_at")[:8]
            )
        else:
            ctx["featured_venues"] = Venue.objects.none()
            ctx["featured_events"] = Event.objects.none()

        # Navegación de categorías
        ctx["active_city_label"] = city.name if city else ""
        ctx["active_city"] = city.slug if city else ""

        def build_url_for_cat(cat_value: str | None):
            params = self.request.GET.copy()
            if ctx["active_city"]:
                params["city"] = ctx["active_city"]
            if cat_value:
                params["cat"] = cat_value
            else:
                params.pop("cat", None)
            params.pop("page", None)
            return "?" + params.urlencode()

        ctx["cat_urls"] = {
            "all":        build_url_for_cat(None),
            "pub":        build_url_for_cat("pub"),
            "restaurant": build_url_for_cat("restaurant"),
            "rooftop":    build_url_for_cat("rooftop"),
            "discoteque": build_url_for_cat("discoteque"),
        }
        return ctx

class CityListView(ListView):
    template_name = "city_index.html"
    context_object_name = "featured_cities"
    paginate_by = 24
    model = Commune

    def get_queryset(self):
        """
        Devuelve las comunas que tienen al menos un venue publicado,
        junto con el conteo de lugares.
        """
        return (
            Commune.objects
            .annotate(
                venues_count=Count(
                    "venues",
                    filter=Q(),
                    distinct=True,
                )
            )
            .filter(venues_count__gt=0)
            .order_by("name")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # ===============================
        # 🔍 Autocomplete (lista de nombres)
        # ===============================
        all_cities = Commune.objects.order_by("name").values_list("name", flat=True)
        ctx["city_names_json"] = json.dumps(list(all_cities), ensure_ascii=False)

        # ===============================
        # 🌆 Adaptar datos al template
        # ===============================
        # El template espera c.url, c.hero_url, c.name, c.venues_count
        try:
            venues_index_url = reverse("venue_index")  # vista que muestra los venues
        except Exception:
            venues_index_url = "/"  # fallback temporal si no existe

        featured = []
        for c in ctx["featured_cities"]:
            featured.append({
                "name": c.name,
                "slug": c.slug,
                "venues_count": getattr(c, "venues_count", 0),
                "hero_url": c.image.url if c.image else "",
                # 👉 Link directo al listado de venues filtrado por ciudad
                "url": f"{venues_index_url}?city={c.slug}",
            })
        ctx["featured_cities"] = featured

        # ===============================
        # 🎯 Variables para el buscador
        # ===============================
        ctx["active_city_label"] = ""  # no hay ciudad activa aún
        ctx["active_when"] = (self.request.GET.get("when") or "cualquier_dia").strip()
        ctx["active_cat"] = (self.request.GET.get("cat") or "").strip()
        ctx["q"] = (self.request.GET.get("q") or "").strip()

        # ===============================
        # 📊 Control de interfaz
        # ===============================
        ctx["venues_count"] = 0     # aquí mostramos ciudades, no venues
        ctx["needs_city"] = True    # evita cargar secciones dependientes de city

        return ctx
    
        
class CityVenueListJsonView(CityVenueListView):
    """Devuelve sólo fragmentos renderizados del mismo city_index.html."""

    def render_to_response(self, context, **response_kwargs):
        try:
            full_html = render_to_string("city_index.html", context, request=self.request)

            def extract_block(block_name):
                pattern = rf"<!-- \[START {block_name}\] -->(.*?)<!-- \[END {block_name}\] -->"
                match = re.search(pattern, full_html, re.S)
                return match.group(1).strip() if match else ""

            featured_html = extract_block("featured_venues")
            grid_html = extract_block("venues_grid")

            return JsonResponse({
                "featured": featured_html,
                "grid": grid_html,
                "count": context.get("venues_count", 0),
            })

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

class FeaturedCitiesView(View):
    """Devuelve HTML del bloque 'Ciudades destacadas' (4 con más venues publicados)."""
    template_name = "city_index.html"

    def get(self, request, *args, **kwargs):
        from django.db.models import Count, Q
        from django.template.loader import render_to_string
        import re

        communes = (
            Commune.objects
            .annotate(venues_count=Count("venues",  filter=Q(), distinct=True))
            .filter(venues_count__gt=0)
            .order_by("-venues_count", "name")[:4]
        )

        featured_cities = []
        for c in communes:
            # 👇 prioriza la imagen del modelo Commune
            hero_url = c.image.url if getattr(c, "image", None) else ""
            city_url = f"{reverse('city_index')}?city={c.slug}"
            featured_cities.append({
                "name": c.name,
                "slug": c.slug,
                "hero_url": hero_url,
                "venues_count": c.venues_count,
                "url": city_url,
            })

        html = render_to_string(self.template_name, {
            "featured_cities": featured_cities,
        }, request=request)

        m = re.search(r"<!-- \[START featured_cities\] -->(.*?)<!-- \[END featured_cities\] -->", html, re.S)
        block_html = m.group(1).strip() if m else ""

        return JsonResponse({"html": block_html})


class EventListView(ListView):
    template_name = "events_index.html"       # tu template
    model = Event
    context_object_name = "events"
    paginate_by = 64  # para poder llenar 4 secciones de 16 c/u (ajústalo si quieres)

    # --- Inicializa siempre atributos usados en el contexto ---
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self._filters = {"q": "", "cat": "", "when": "proximos"}
        self._city = None

    # -------- helpers --------
    def _resolve_city(self, raw: str | None):
        """Acepta nombre o slug; si no viene, fallback a Santiago."""
        raw = (raw or "").strip()
        if raw:
            c = Commune.objects.filter(
                Q(name__iexact=raw) | Q(slug__iexact=slugify(raw))
            ).first()
            if c:
                return c
        return Commune.objects.filter(
            Q(slug__iexact="santiago") | Q(name__iexact="Santiago")
        ).first()

    def _when_bounds(self, when: str):
        """Devuelve (start, end) aware para los filtros temporales."""
        tz = timezone.get_current_timezone()
        now = timezone.now().astimezone(tz)

        def day_bounds(d):
            start = timezone.make_aware(datetime.combine(d, time.min), tz)
            end   = timezone.make_aware(datetime.combine(d + timedelta(days=1), time.min), tz)
            return start, end

        if when == "hoy":
            return day_bounds(now.date())
        if when == "manana":
            return day_bounds(now.date() + timedelta(days=1))
        if when == "esta_semana":
            monday = now - timedelta(days=now.weekday())  # lunes de esta semana
            start = timezone.make_aware(datetime.combine(monday.date(), time.min), tz)
            end   = start + timedelta(days=7)
            return start, end
        if when == "finde":
            friday = (now - timedelta(days=now.weekday())) + timedelta(days=4)  # viernes
            start = timezone.make_aware(datetime.combine(friday.date(), time.min), tz)
            end   = start + timedelta(days=3)  # hasta lunes 00:00
            return start, end

        # por defecto: próximos 60 días
        start = now
        end   = now + timedelta(days=60)
        return start, end

    # -------- queryset --------
    def get_queryset(self):
        req   = self.request.GET
        q     = (req.get("q") or "").strip()
        cat   = (req.get("cat") or "").strip()
        when  = (req.get("when") or "proximos").strip()
        city  = self._resolve_city(req.get("city"))

        qs = (
            Event.objects.select_related("venue", "Commune")
            .filter(is_published=True)
            .order_by("start_at")
        )

        # ciudad
        if city:
            qs = qs.filter(Commune=city)

        # rango temporal
        start, end = self._when_bounds(when)
        qs = qs.filter(start_at__gte=start, start_at__lt=end)

        # categoría
        if cat:
            qs = qs.filter(category=cat)

        # búsqueda
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(venue__name__icontains=q) |
                Q(Commune__name__icontains=q)
            )

        # Guarda para el contexto
        self._city = city
        self._filters = {"q": q, "cat": cat, "when": when}
        return qs

    # -------- contexto --------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Respaldos seguros
        filters = getattr(self, "_filters", {"q": "", "cat": "", "when": "proximos"})
        city = getattr(self, "_city", None)

        q    = filters.get("q", "")
        cat  = filters.get("cat", "")
        when = filters.get("when", "proximos")

        # CTA + flag promoted (efímeros) para los objetos de la página actual
        for e in ctx["page_obj"].object_list:
            # CTA
            ext = (getattr(e, "external_ticket_url", "") or "").strip()
            if ext:
                e.cta_url = ext
                e.cta_is_external = True
                e.cta_label = "Comprar entradas"
            else:
                if e.venue:
                    e.cta_url = reverse("venue-detail", kwargs={"slug": e.venue.slug})
                    e.cta_is_external = False
                    e.cta_label = "Ver venue"
                else:
                    e.cta_url = reverse("home")
                    e.cta_is_external = False
                    e.cta_label = "Ver más"

            # Flag usado por tu JS para “Publicitados”
            # (tu modelo tiene is_featured; lo exponemos como is_promoted temporalmente)
            e.is_promoted = bool(getattr(e, "is_featured", False))

        # Filtros activos
        ctx["q"] = q
        ctx["active_cat"] = cat
        ctx["active_when"] = when

        # Ciudad activa
        ctx["city"] = city
        ctx["active_city_label"] = city.name if city else ""
        ctx["active_city"] = city.slug if city else ""

        # Conteo total (de la consulta, no solo de la página)
        ctx["total"] = ctx.get("paginator").count if ctx.get("paginator") else 0

        # JSON de comunas para autocompletar (name + slug)
        # Usa un subconjunto si tienes muchas comunas para no inflar el HTML.
        communes_qs = Commune.objects.only("name", "slug").order_by("name")
        ctx["communes_json"] = json.dumps(
            [{"name": c.name, "slug": c.slug} for c in communes_qs],
            ensure_ascii=False
        )

        # URLs de categorías (por si las mantienes)
        def build_url_for_cat(val: str | None):
            params = self.request.GET.copy()
            if city:
                params["city"] = city.slug
            if val:
                params["cat"] = val
            else:
                params.pop("cat", None)
            params.pop("page", None)
            return "?" + params.urlencode()

        ctx["cat_urls"] = {
            "all":        build_url_for_cat(None),
            "party":      build_url_for_cat("party"),
            "concert":    build_url_for_cat("concert"),
            "standup":    build_url_for_cat("standup"),
            "electronic": build_url_for_cat("electronic"),
            "other":      build_url_for_cat("other"),
        }

        return ctx
    
    

def track_click(request):
    model = request.POST.get("model")   # "venue" | "event"
    pk    = request.POST.get("id")      # id numérico
    if model not in {"venue", "event"} or not pk:
        raise Http404("Parámetros inválidos")

    # Asegura session_key para anónimos
    if not request.session.session_key:
        request.session.save()

    # Dedupe por usuario/sesión + IP
    user_scope = (
        f"user:{request.user.pk}" if request.user.is_authenticated
        else f"session:{request.session.session_key}"
    )
    ip = request.META.get("REMOTE_ADDR", "ip:unknown")
    dedupe_id = f"{user_scope}:{ip}"

    key = f"clickdedupe:{model}:{pk}:{dedupe_id}"
    if cache.get(key):
        return JsonResponse({"ok": True, "deduped": True})

    obj = get_object_or_404(Venue if model == "venue" else Event, pk=pk)
    type(obj).objects.filter(pk=obj.pk).update(
        clicks_count=F("clicks_count") + 1,
        last_clicked_at=timezone.now()
    )

    cache.set(key, 1, timeout=30*60)
    return JsonResponse({"ok": True})


PLAN_TITLE = "Midnight – Plan Mensual"
PLAN_PRICE = 5990.0  # CLP


class SubscribeView(LoginRequiredMixin, TemplateView):
    template_name = "billing/subscribe.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sub = getattr(self.request.user, "subscription", None)
        ctx["is_active"] = bool(sub and sub.is_active())
        return ctx


class SubscribeConfirmView(LoginRequiredMixin, View):
    def post(self, request):
        preapproval_id = (request.POST.get("preapproval_id") or "").strip()
        status = (request.POST.get("status") or "approved").lower()

        if not preapproval_id:
            return HttpResponseBadRequest("missing preapproval_id")

        sub, _ = Subscription.objects.get_or_create(user=request.user)

        # Guarda el identificador de suscripción de MP para conciliaciones y futuras cancelaciones
        if hasattr(sub, "mp_preapproval_id"):
            sub.mp_preapproval_id = preapproval_id

        # Activa tu lógica local
        now = timezone.now()
        end = now + timedelta(days=30)

        if hasattr(sub, "override_status"):
            sub.override_status = Subscription.ACTIVE
            sub.override_until = end
            sub.override_reason = f"MP preapproval: {preapproval_id}"

        if hasattr(sub, "status"):
            sub.status = Subscription.ACTIVE
        if hasattr(sub, "current_period_end"):
            sub.current_period_end = end

        sub.save()
        return JsonResponse({"ok": True})


class AccountDeleteView(LoginRequiredMixin, View):
    """
    Cancela la suscripción recurrente en MP (si existe) y elimina la cuenta del usuario.
    Redirige a 'account_deleted'.
    """
    def get(self, request):
        return HttpResponseNotAllowed(["POST"])

    @transaction.atomic
    def post(self, request):
        user = request.user
        # 1) Intentar cancelar preaprobación en Mercado Pago
        try:
            sub = getattr(user, "subscription", None)
            preapproval_id = getattr(sub, "mp_preapproval_id", None)
            access_token = getattr(settings, "MP_ACCESS_TOKEN", "").strip()

            if preapproval_id and access_token:
                sdk = mercadopago.SDK(access_token)
                # Estado válido para cancelar: "cancelled"
                _ = sdk.preapproval().update(preapproval_id, {"status": "cancelled"})

                # Marcar localmente como inactiva
                if hasattr(sub, "override_status"):
                    # Ajusta el valor INACTIVE/CANCELED según tu enum/modelo
                    try:
                        sub.override_status = getattr(Subscription, "INACTIVE", getattr(Subscription, "CANCELED", 0))
                    except Exception:
                        sub.override_status = 0
                    sub.override_until = timezone.now()
                    sub.override_reason = f"Cancelada por el usuario al eliminar cuenta. preapproval_id={preapproval_id}"

                if hasattr(sub, "status"):
                    try:
                        sub.status = getattr(Subscription, "INACTIVE", getattr(Subscription, "CANCELED", 0))
                    except Exception:
                        sub.status = 0
                if hasattr(sub, "current_period_end"):
                    sub.current_period_end = timezone.now()

                sub.save()
        except Exception:
            # Si falla la cancelación en MP, continuamos con la eliminación para no bloquear al usuario.
            pass

        # 2) Eliminar la cuenta
        # Primero cerramos sesión para limpiar autenticación
        logout(request)
        # Luego borramos el usuario (esto puede borrar en cascada perfiles si están en on_delete=CASCADE)
        user.delete()

        # 3) Redirigir a una confirmación (no usamos messages porque la sesión se cerró)
        return redirect("account_deleted")


class AccountDeletedView(TemplateView):
    template_name = "accounts/account_deleted.html"


class VenueCreateView(LoginRequiredMixin, CreateView):
    """Permite a un dueño agregar una nueva sucursal (Venue)."""
    model = Venue
    form_class = VenueCreateForm
    template_name = "venue_create.html"
    context_object_name = "venue"

    def form_valid(self, form):
        venue = form.save(commit=False)
        venue.owner_user = self.request.user
        base = f"{venue.name}-{venue.Commune.name if venue.Commune else ''}"
        venue.slug = slugify(base)[:210]
        venue.save()
        form.save_m2m()
        messages.success(self.request, "Sucursal agregada correctamente 🎉")
        return redirect(reverse("venue-detail", kwargs={"slug": venue.slug}))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Agregar nueva sucursal"
        # JSON ligero para el datalist: id, name, slug
        communes = Commune.objects.order_by("name").values("id", "name", "slug")
        ctx["communes_json"] = json.dumps(list(communes), cls=DjangoJSONEncoder, ensure_ascii=False)
        return ctx
    
