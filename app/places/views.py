from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Case, When, Value, IntegerField
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, DetailView, UpdateView, ListView, DeleteView, CreateView
from django.views.generic.edit import FormMixin
from .forms import VenueForm, VenueUpdateForm, EventForm, VenueGalleryUploadForm
from .models import Venue, Event, Photo, Tag
from datetime import datetime, timedelta, time
import json
from django.utils.text import slugify
from django.http import QueryDict
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from django.views.generic import ListView
from .models import Venue, Event, Commune
# views.py
from django.views.generic import TemplateView
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta, time

from .models import Commune, Venue, Event

class HomeView(TemplateView):
    template_name = "index.html"

    # --- Helpers de fecha ---
    def _today_range(self, tz):
        today = timezone.localdate()
        start = timezone.make_aware(datetime.combine(today, time.min), tz)
        end   = start + timedelta(days=1)
        return start, end

    def _tomorrow_range(self, tz):
        today = timezone.localdate() + timedelta(days=1)
        start = timezone.make_aware(datetime.combine(today, time.min), tz)
        end   = start + timedelta(days=1)
        return start, end

    def _weekend_range(self, tz):
        # Viernes a domingo de ESTA semana (si ya pasó domingo, próximo finde)
        today = timezone.localdate()
        weekday = today.weekday()  # 0=Lunes ... 6=Domingo
        # próximo viernes relativo
        days_to_friday = (4 - weekday) % 7
        friday = today + timedelta(days=days_to_friday)
        start = timezone.make_aware(datetime.combine(friday, time.min), tz)
        end   = start + timedelta(days=3)  # exclusivo (vie 00:00 → lun 00:00)
        return start, end

    # --- Resolución de ciudad (por ?city=slug|nombre). Si no, primera comuna ---
    def _get_city(self, request):
        city_raw = (request.GET.get("city") or "").strip()
        if city_raw:
            slugguess = city_raw  # si ya viene slug
            commune = Commune.objects.filter(
                Q(slug__iexact=slugguess) | Q(name__iexact=city_raw)
            ).first()
            if commune:
                return commune
        return Commune.objects.order_by("name").first()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tz = timezone.get_current_timezone()

        city = self._get_city(self.request)  # puede ser None si DB vacía
        ctx["city"] = city
        ctx["active_city_label"] = city.name if city else "Chile"
        ctx["active_city"] = city.slug if city else ""

        # ---------- Trending de hoy (mezcla simple: eventos de hoy + venues publicados) ----------
        trending_items = []
        if city:
            # Eventos de HOY en la comuna
            t_start, t_end = self._today_range(tz)
            events_today = (
                Event.objects
                .filter(is_published=True, Commune=city, start_at__gte=t_start, start_at__lt=t_end)
                .select_related("venue")
                .order_by("start_at")[:16]
            )
            for e in events_today:
                img = (e.flyer_image.url if e.flyer_image else (e.venue.cover_image.url if e.venue and e.venue.cover_image else ""))
                trending_items.append({
                    "type": "evento",
                    "title": e.title,
                    "time": timezone.localtime(e.start_at).strftime("%a %H:%M"),
                    "venue": (e.venue.name if e.venue else city.name),
                    "href": self.request.build_absolute_uri(
                        # ajusta si tu urlpattern es distinto
                        reverse("event_detail", kwargs={"slug": e.slug})
                    ),
                    "badge": e.badge_text or "Hoy",
                    "badgeVariant": "primary",
                    "img": img or "",
                })

            # Venues publicados (fallback visual)
            venues = (
                Venue.objects
                .filter(is_published=True, Commune=city)
                .order_by("name")[:16]
            )
            for v in venues:
                trending_items.append({
                    "type": "lugar",
                    "title": v.name,
                    "time": v.hours_short or "",
                    "venue": v.Commune.name,
                    "href": self.request.build_absolute_uri(
                        reverse("venue-detail", kwargs={"slug": v.slug})
                    ),
                    "badge": v.get_category_display(),
                    "badgeVariant": "secondary",
                    "img": (v.cover_image.url if v.cover_image else (v.gallery_venue.url if v.gallery_venue else "")),
                })

        # Chunks de 4 (para el carrusel)
        chunks = []
        per = 4
        for i in range(0, len(trending_items), per):
            chunks.append(trending_items[i:i+per])
        ctx["trending_chunks"] = chunks

        # ---------- “Próximos eventos destacados” (SEO): is_featured + próximos ----------
        featured_events = Event.objects.none()
        if city:
            now = timezone.now()
            featured_events = (
                Event.objects
                .filter(is_published=True, Commune=city, start_at__gte=now, is_featured=True)
                .select_related("venue")
                .order_by("feature_order", "start_at")[:9]
            )
        ctx["featured_events"] = featured_events

        # ---------- Tabs: Hoy / Mañana / Finde ----------
        ctx["events_hoy"] = Event.objects.none()
        ctx["events_manana"] = Event.objects.none()
        ctx["events_finde"] = Event.objects.none()
        if city:
            h_s, h_e   = self._today_range(tz)
            m_s, m_e   = self._tomorrow_range(tz)
            f_s, f_e   = self._weekend_range(tz)

            ctx["events_hoy"] = (
                Event.objects
                .filter(is_published=True, Commune=city, start_at__gte=h_s, start_at__lt=h_e)
                .select_related("venue")
                .order_by("start_at")[:12]
            )
            ctx["events_manana"] = (
                Event.objects
                .filter(is_published=True, Commune=city, start_at__gte=m_s, start_at__lt=m_e)
                .select_related("venue")
                .order_by("start_at")[:12]
            )
            ctx["events_finde"] = (
                Event.objects
                .filter(is_published=True, Commune=city, start_at__gte=f_s, start_at__lt=f_e)
                .select_related("venue")
                .order_by("start_at")[:12]
            )

        # ---------- Top lugares en {Ciudad} ----------
        ctx["top_venues"] = Venue.objects.none()
        if city:
            ctx["top_venues"] = (
                Venue.objects
                .filter(is_published=True, Commune=city)
                .order_by("name")[:8]
            )

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
    template_name = "detail.html"
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
            .filter(is_published=True, venue=v)
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
            .filter(is_published=True, venue=v, start_at__gte=now)
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




class CityVenueListView(ListView):
    template_name = "city_index.html"
    context_object_name = "venues"
    paginate_by = 24
    model = Venue

    def _get_week_range_next_monday_to_sunday(self, tz):
        """Rango de la PRÓXIMA semana (lunes a domingo) en timezone local."""
        now = timezone.now().astimezone(tz)
        days_until_next_monday = (7 - now.weekday()) % 7 or 7
        next_monday = (now + timedelta(days=days_until_next_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_end = next_monday + timedelta(days=7)  # exclusivo
        return next_monday, week_end

    def get_queryset(self):
        qs = Venue.objects.select_related("Commune")   #.filter(is_published=True)

        q        = (self.request.GET.get("q") or "").strip()
        cat      = (self.request.GET.get("cat") or "").strip()
        when     = (self.request.GET.get("when") or "cualquier_dia").strip()
        city_raw = (self.request.GET.get("city") or "").strip()   # ✅ FALTABA

        # 1) Sin ciudad → no listar (template puede mostrar recomendados)
        if not city_raw:
            self.needs_city = True
            self.city_input_value = ""
            self.filter_city = None
            return Venue.objects.none()

        # 2) Validar ciudad por nombre o slug
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

        # 4) Texto libre
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(description__icontains=q) |
                Q(address__icontains=q)
            )

        # 5) Categoría
        if cat:
            qs = qs.filter(category=cat)

        # 6) Fecha (filtra venues que tengan eventos en el rango)
        tz = timezone.get_current_timezone()

        if when == "hoy":
            today = timezone.localdate()
            start = timezone.make_aware(datetime.combine(today, time.min), tz)
            end   = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min), tz)
            qs = qs.filter(
                events__is_published=True,
                events__start_at__gte=start,
                events__start_at__lt=end
            ).distinct()

        elif when == "esta_semana":
            start, end = self._get_week_range_next_monday_to_sunday(tz)
            qs = qs.filter(
                events__is_published=True,
                events__start_at__gte=start,
                events__start_at__lt=end
            ).distinct()

        # else: "cualquier_dia" -> no filtrar por eventos

        return qs.order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        req = self.request.GET

        # ✅ aseguramos que la clave city exista ANTES de usarla en el mapa
        ctx["city"] = getattr(self, "filter_city", None)

        # ==========================
        # 🌍 Datos del mapa
        # ==========================
        center = {"lat": -33.4489, "lon": -70.6693}  # fallback Santiago
        city = ctx["city"]
        if city and getattr(city, "lat", None) and getattr(city, "lon", None):
            center = {"lat": float(city.lat), "lon": float(city.lon)}

        venues_map = []
        for v in ctx["object_list"]:
            if v.address:
                venues_map.append({
                    "slug": v.slug,
                    "name": v.name,
                    "category": v.get_category_display(),
                    "address": v.address,
                    "city": v.Commune.name if v.Commune_id else "",
                    "country": "Chile",
                    "cover": (v.cover_image.url if v.cover_image else ""),
                    "q": f"{v.address}, {v.Commune.name if v.Commune_id else ''}, Chile".strip(", "),
                    "url": self.request.build_absolute_uri(reverse("venue-detail", kwargs={"slug": v.slug})),
                })

        ctx["map_center_json"] = json.dumps(center)
        ctx["venues_map_json"] = json.dumps(venues_map, ensure_ascii=False)

        # ==========================
        # 🔍 Filtros activos
        # ==========================
        ctx["q"] = (req.get("q") or "").strip()
        ctx["active_cat"]  = (req.get("cat") or "").strip()
        ctx["active_when"] = (req.get("when") or "").strip()
        ctx["city_input_value"] = getattr(self, "city_input_value", "")

        # ✅ mantener todas las comunas (para el buscador)
        cities_qs = Commune.objects.order_by("name")
        ctx["city_names_json"] = json.dumps(
            list(cities_qs.values_list("name", flat=True)),
            ensure_ascii=False
        )

        ctx["needs_city"]   = getattr(self, "needs_city", False)
        ctx["error_city"]   = getattr(self, "error_city", "")
        ctx["venues_count"] = ctx["object_list"].count() if not ctx["needs_city"] else 0

        # ==========================
        # ⭐ Secciones destacadas
        # ==========================
        if city:
            ctx["featured_venues"] = (
                Venue.objects
                    .filter(Commune=city, is_published=True)
                    .order_by("name")[:4]
            )
            ctx["featured_events"] = (
                Event.objects
                    .filter(Commune=city, is_published=True, venue__isnull=False, venue__is_published=True)
                    .select_related("venue")
                    .order_by("start_at")[:4]
            )
        else:
            ctx["featured_venues"] = Venue.objects.none()
            ctx["featured_events"] = Event.objects.none()

        # ==========================
        # 🧭 Valores activos + URLs categorías
        # ==========================
        ctx["active_city_label"] = city.name if city else ""
        ctx["active_city"] = city.slug if city else ""

        def build_url_for_cat(cat_value: str | None):
            params = self.request.GET.copy()

            # fuerza ciudad actual en slug si existe
            if ctx["active_city"]:
                params["city"] = ctx["active_city"]

            # set/clear cat
            if cat_value:
                params["cat"] = cat_value
            else:
                params.pop("cat", None)

            # limpia paginación
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

    
        
# views.py
from django.http import JsonResponse
from django.template.loader import render_to_string
import re

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



# views.py
from django.views.generic import View
from django.http import JsonResponse
from django.db.models import Count, Q
from django.urls import reverse

class FeaturedCitiesView(View):
    """Devuelve HTML del bloque 'Ciudades destacadas' (4 con más venues publicados)."""
    template_name = "city_index.html"

    def get(self, request, *args, **kwargs):
        from django.db.models import Count, Q
        from django.template.loader import render_to_string
        import re

        communes = (
            Commune.objects
            .annotate(venues_count=Count("venues", filter=Q(venues__is_published=True)))
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

