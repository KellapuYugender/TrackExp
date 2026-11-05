
from django.urls import path
from rest_framework_simplejwt.views import (TokenObtainPairView,TokenRefreshView,)
from .views import RegisterView, MeView,TripListCreateView,TripDetailView


urlpatterns = [
    # Keep any existing API routes here.

    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("trips/", TripListCreateView.as_view(), name="trip-list-create"),
    path("trips/<int:pk>/", TripDetailView.as_view(), name="trip-detail"),
]
