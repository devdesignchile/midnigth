from django.urls import path
from .views import HomeView, VenueDetailView, VenueUpdateView, MyVenuesListView, EventCreateView, EventUpdateView, VenueGalleryUploadView, CityVenueListView
from .views import CityVenueListView, CityVenueListJsonView, FeaturedCitiesView, VenueSearchView, EventListView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("buscar/", VenueSearchView.as_view(), name="venue_search"),
    path("owner/mis-negocios/", MyVenuesListView.as_view(), name="list_venues-owner"),
    path("lugar/<slug:slug>/", VenueDetailView.as_view(), name="venue-detail"),
    path("lugar/<slug:slug>/editar/", VenueUpdateView.as_view(), name="venue-update"),
    path("lugar/<slug:slug>/events/new/", EventCreateView.as_view(), name="event_create"),
    path("lugar/<slug:slug>/events/<int:pk>/editar/", EventUpdateView.as_view(), name="event_edit"),
    path("lugar/<slug:slug>/galeria/subir/", VenueGalleryUploadView.as_view(), name="venue-gallery-upload"),
    path("ciudad/", CityVenueListView.as_view(), name="city-detail"),
    path("city/", CityVenueListView.as_view(), name="city_index"),
    path("city/json/", CityVenueListJsonView.as_view(), name="city_index_json"),
    path("city/featured/", FeaturedCitiesView.as_view(), name="city_featured"),
    path("eventos/", EventListView.as_view(), name="events-detail"),
]