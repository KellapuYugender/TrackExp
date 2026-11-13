
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.shortcuts import get_object_or_404
from .serializers import RegisterSerializer, UserProfileSerializer,TripSerializer,ContributionSerializer,ExpenseSerializer
from .models import Trip,Contribution,Expense
from django.db import transaction



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


class ExpenseListCreateView(generics.ListCreateAPIView):
    serializer_class = ExpenseSerializer
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

        return Expense.objects.filter(
            trip=trip
        ).select_related("paid_by", "recorded_by")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["trip"] = self.get_trip()
        return context

    @transaction.atomic
    def perform_create(self, serializer):
        trip = Trip.objects.select_for_update().get(
            pk=self.get_trip().pk
        )

        # Recheck the available balance while holding the trip lock.
        if trip.status != Trip.Status.ACTIVE:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                "Cannot add expenses to a closed trip."
            )

        if serializer.validated_data["amount"] > trip.remaining_balance:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                "amount": "Insufficient shared fund balance."
            })

        serializer.save()

    
