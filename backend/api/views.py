
from rest_framework import generics,status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .serializers import RegisterSerializer, UserProfileSerializer,TripSerializer,ContributionSerializer,ExpenseSerializer,TripInvitationSerializer,TripMemberSerializer
from .models import Trip,Contribution,Expense,TripMember,TripInvitation
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

    

class TripInvitationListCreateView(generics.ListCreateAPIView):
    serializer_class = TripInvitationSerializer
    permission_classes = [IsAuthenticated]

    def get_trip(self):
        trip = get_object_or_404(
            Trip,
            pk=self.kwargs["trip_id"]
        )

        is_admin = TripMember.objects.filter(
            trip=trip,
            user=self.request.user,
            role=TripMember.Role.ADMIN
        ).exists()

        if not is_admin:
            raise PermissionDenied(
                "Only trip admins can manage invitations."
            )

        return trip

    def get_queryset(self):
        trip = self.get_trip()

        return TripInvitation.objects.filter(
            trip=trip
        ).order_by("-created_at")

    def perform_create(self, serializer):
        trip = self.get_trip()

        if trip.status != Trip.Status.ACTIVE:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                "Cannot create invitations for a closed trip."
            )

        serializer.save(
            trip=trip,
            created_by=self.request.user
        )


class JoinTripView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        token = request.data.get("token")

        if not isinstance(token, str) or not token.strip():
            return Response(
                {"error": "Invitation token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        invitation = (
            TripInvitation.objects
            .select_related("trip")
            .select_for_update()
            .filter(token=token.strip())
            .first()
        )

        if invitation is None:
            return Response(
                {"error": "Invalid invitation token."},
                status=status.HTTP_400_BAD_REQUEST
            )

        trip = invitation.trip

        if not invitation.is_valid:
            return Response(
                {"error": "Invitation has expired or is inactive."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if trip.status != Trip.Status.ACTIVE:
            return Response(
                {"error": "Cannot join a closed trip."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if TripMember.objects.filter(
            trip=trip,
            user=request.user
        ).exists():
            return Response(
                {"error": "You are already a member of this trip."},
                status=status.HTTP_400_BAD_REQUEST
            )

        TripMember.objects.create(
            trip=trip,
            user=request.user,
            role=TripMember.Role.MEMBER
        )

        return Response(
            {
                "message": "Successfully joined the trip.",
                "trip_id": trip.id,
                "trip_name": trip.name,
                "role": TripMember.Role.MEMBER
            },
            status=status.HTTP_201_CREATED
        )


class TripMemberListView(generics.ListAPIView):
    serializer_class = TripMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        trip = get_object_or_404(
            Trip.objects.filter(
                members__user=self.request.user
            ),
            pk=self.kwargs["trip_id"]
        )

        return TripMember.objects.filter(
            trip=trip
        ).select_related("user").order_by("joined_at", "id")
