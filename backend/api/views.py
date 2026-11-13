
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.shortcuts import get_object_or_404
from .serializers import RegisterSerializer, UserProfileSerializer,TripSerializer,ContributionSerializer
from .models import Trip,Contribution



class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class MeView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class TripListCreateView(generics.ListCreateAPIView):
    serializer_class = TripSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        return Trip.objects.filter(
            members__user=user
        ).distinct()

class TripDetailView(generics.RetrieveAPIView):
    serializer_class = TripSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Trip.objects.filter(
            members__user=self.request.user
        )    


class ContributionListCreateView(generics.ListCreateAPIView):
    serializer_class = ContributionSerializer
    permission_classes = [IsAuthenticated]

    def get_trip(self):
        return get_object_or_404(
            Trip.objects.filter(
                members__user=self.request.user
            ),
            pk=self.kwargs["trip_id"]
        )

    def get_queryset(self):
        trip = self.get_trip()

        return Contribution.objects.filter(
            trip=trip
        ).select_related("member__user", "recorded_by")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["trip"] = self.get_trip()
        return context
    
