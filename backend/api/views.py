
from rest_framework import generics,status
from rest_framework.permissions import AllowAny, IsAuthenticated
from decimal import Decimal
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied,ValidationError,NotFound
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .serializers import (
    RegisterSerializer, UserProfileSerializer,
    TripSerializer,ContributionSerializer,
    ExpenseSerializer,TripInvitationSerializer,
    TripMemberSerializer,TripSettlementSerializer,
    TripTopUpRequestSerializer,TripTopUpShareSerializer,TopUpContributionSerializer)
from .models import (
    Trip,Contribution,
    Expense,TripMember,
    TripInvitation,TripSettlement,
    TripTopUpShare,TripTopUpRequest)
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

    @transaction.atomic
    def perform_create(self, serializer):
        trip = Trip.objects.select_for_update().get(
            pk=self.get_trip().pk
        )

        if trip.status != Trip.Status.ACTIVE:
            raise ValidationError(
                "Cannot add contributions to a closed trip."
            )

        serializer.save()
    

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

        if trip.status != Trip.Status.ACTIVE:
            raise ValidationError(
                "Cannot add expenses to a closed trip."
            )

        amount = serializer.validated_data["amount"]

        if amount > trip.remaining_balance:
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



class CloseTripView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, trip_id):
        trip = Trip.objects.select_for_update().filter(
            pk=trip_id,
            members__user=request.user,
            members__role=TripMember.Role.ADMIN
        ).first()

        if trip is None:
            raise PermissionDenied(
                "Only trip admins can close this trip."
            )

        if trip.status == Trip.Status.CLOSED:
            raise ValidationError(
                "This trip is already closed."
            )

        members = list(
            TripMember.objects.filter(
                trip=trip
            ).select_related("user").order_by("id")
        )

        if not members:
            raise ValidationError(
                "Cannot close a trip without members."
            )

        remaining = trip.remaining_balance

        if remaining < Decimal("0.00"):
            raise ValidationError(
                "Cannot close a trip with a negative balance."
            )

        # Convert balance to cents.
        total_cents = int(remaining * 100)

        base_cents, extra_cents = divmod(
            total_cents, len(members)
        )

        payouts = []

        for index, member in enumerate(members):
            cents = base_cents + (
                1 if index < extra_cents else 0
            )

            amount = Decimal(cents) / Decimal("100")
            amount = amount.quantize(Decimal("0.01"))

            # Save settlement for EACH member.
            TripSettlement.objects.create(
                trip=trip,
                member=member,
                amount=amount
            )

            # Add EACH member to API response.
            payouts.append({
                "user_id": member.user_id,
                "username": member.user.username,
                "amount": str(amount)
            })

        # Close trip after saving all settlements.
        trip.status = Trip.Status.CLOSED
        trip.closed_at = timezone.now()

        trip.save(
            update_fields=["status", "closed_at"]
        )

        return Response(
            {
                "message": "Trip closed successfully.",
                "trip_id": trip.id,
                "trip_name": trip.name,
                "status": trip.status,
                "total_contributions": str(
                    trip.total_contributions
                ),
                "total_expenses": str(
                    trip.total_expenses
                ),
                "remaining_balance": str(remaining),
                "member_count": len(members),
                "payouts": payouts
            },
            status=status.HTTP_200_OK
        )


class TripSettlementListView(generics.ListAPIView):
    serializer_class = TripSettlementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        trip_id = self.kwargs["trip_id"]

        trip = Trip.objects.filter(
            pk=trip_id,
            members__user=self.request.user
        ).first()

        if trip is None:
            raise NotFound("Trip not found.")

        return (
            TripSettlement.objects.filter(trip=trip)
            .select_related("member__user")
            .order_by("member_id")
        )


class TripTopUpListCreateView(generics.ListCreateAPIView):
    serializer_class = TripTopUpRequestSerializer
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

        return (
            TripTopUpRequest.objects.filter(trip=trip)
            .select_related("created_by")
            .prefetch_related("shares__member__user")
            .order_by("-created_at")
        )

    @transaction.atomic
    def perform_create(self, serializer):
        trip = Trip.objects.select_for_update().get(
            pk=self.get_trip().pk
        )

        if trip.status != Trip.Status.ACTIVE:
            raise ValidationError(
                "Cannot create top-up requests for a closed trip."
            )

        is_admin = TripMember.objects.filter(
            trip=trip,
            user=self.request.user,
            role=TripMember.Role.ADMIN
        ).exists()

        if not is_admin:
            raise PermissionDenied(
                "Only trip admins can create top-up requests."
            )

        members = list(
            TripMember.objects.filter(trip=trip)
            .select_related("user")
            .order_by("id")
        )

        if not members:
            raise ValidationError(
                "Cannot create a top-up without members."
            )

        total_amount = serializer.validated_data["total_amount"]
        total_cents = int(total_amount * 100)

        # Each member receives an equal target,
        # with leftover cents distributed in member ID order.
        base_cents, extra_cents = divmod(
            total_cents,
            len(members)
        )

        # Every member must have a positive target.
        if base_cents == 0:
            raise ValidationError({
                "total_amount": (
                    "Amount must be at least $0.01 per member."
                )
            })

        topup = serializer.save(
            trip=trip,
            created_by=self.request.user
        )

        shares = []

        for index, member in enumerate(members):
            cents = base_cents + (
                1 if index < extra_cents else 0
            )

            shares.append(
                TripTopUpShare(
                    topup_request=topup,
                    member=member,
                    target_amount=(
                        Decimal(cents) / Decimal("100")
                    )
                )
            )

        TripTopUpShare.objects.bulk_create(shares)

        # Refresh nested shares for the response.
        topup.refresh_from_db()


class TopUpContributeView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, trip_id, topup_id):
        trip = get_object_or_404(
            Trip.objects.select_for_update(),
            pk=trip_id,
            members__user=request.user
        )

        if trip.status != Trip.Status.ACTIVE:
            raise ValidationError("Trip is closed.")

        topup = get_object_or_404(
            TripTopUpRequest.objects.select_for_update(),
            pk=topup_id,
            trip=trip
        )

        if topup.status != TripTopUpRequest.Status.ACTIVE:
            raise ValidationError(
                "This top-up request is not active."
            )

        member = get_object_or_404(
            TripMember,
            trip=trip,
            user=request.user
        )

        share = get_object_or_404(
            TripTopUpShare.objects.select_for_update(),
            topup_request=topup,
            member=member
        )

        serializer = TopUpContributionSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data["amount"]

        if amount > share.remaining_amount:
            raise ValidationError({
                "amount": "Amount exceeds your remaining target."
            })

        contribution = Contribution.objects.create(
            trip=trip,
            member=member,
            recorded_by=request.user,
            amount=amount,
            note=serializer.validated_data["note"],
            topup_share=share
        )

        all_shares = list(
            TripTopUpShare.objects.filter(
                topup_request=topup
            )
        )

        if all(
            item.remaining_amount == Decimal("0.00")
            for item in all_shares
        ):
            topup.status = TripTopUpRequest.Status.COMPLETED
            topup.save(update_fields=["status"])

        return Response(
            {
                "message": "Top-up contribution recorded.",
                "contribution_id": contribution.id,
                "amount": str(contribution.amount),
                "paid_amount": str(share.paid_amount),
                "remaining_target": str(share.remaining_amount),
                "topup_status": topup.status,
                "trip_remaining_balance": str(
                    trip.remaining_balance
                )
            },
            status=status.HTTP_201_CREATED
        )
