
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from django.db import transaction
from .models import Trip,TripMember,Contribution,Expense,TripInvitation,TripSettlement,TripTopUpRequest,TripTopUpShare
from decimal import Decimal

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def validate_email(self, value):
        value = value.strip().lower()

        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]
        read_only_fields = fields


class TripSerializer(serializers.ModelSerializer):
    total_contributions = serializers.DecimalField(
    max_digits=14,
    decimal_places=2,
    read_only=True
)

    total_expenses = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True
    )

    remaining_balance = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True
    )
    class Meta:
        model = Trip
        fields = [
            "id",
            "name",
            "description",
            "start_date",
            "end_date",
            "currency",
            "status",
            "created_by",
            "created_at",
            "total_contributions",
            "total_expenses",
            "remaining_balance",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_by",
            "created_at",
        ]

    def validate(self, data):
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date cannot be before start date."
            })

        return data

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user

        trip = Trip.objects.create(
            created_by=user,
            **validated_data
        )

        TripMember.objects.create(
            trip=trip,
            user=user,
            role=TripMember.Role.ADMIN
        )

        return trip


class ContributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contribution
        fields = [
            "id",
            "trip",
            "member",
            "recorded_by",
            "amount",
            "note",
            "contributed_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "trip",
            "recorded_by",
            "created_at",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Contribution amount must be greater than zero."
            )
        return value

    def validate(self, data):
        trip = self.context["trip"]
        member = data["member"]
        user = self.context["request"].user

        if trip.status != Trip.Status.ACTIVE:
            raise serializers.ValidationError(
                "Cannot contribute to a closed trip."
            )

        if member.trip_id != trip.id:
            raise serializers.ValidationError({
                "member": "This member does not belong to the trip."
            })

        if not TripMember.objects.filter(
            trip=trip,
            user=user,
        ).exists():
            raise serializers.ValidationError(
                "You must belong to this trip to record contributions."
            )

        return data

    def create(self, validated_data):
        return Contribution.objects.create(
            trip=self.context["trip"],
            recorded_by=self.context["request"].user,
            **validated_data,
        )


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            "id",
            "trip",
            "paid_by",
            "recorded_by",
            "amount",
            "merchant",
            "location",
            "description",
            "category",
            "spent_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "trip",
            "recorded_by",
            "created_at",
            "updated_at",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Expense amount must be greater than zero."
            )
        return value

    def validate(self, data):
        trip = self.context["trip"]
        user = self.context["request"].user
        paid_by = data["paid_by"]

        if trip.status != Trip.Status.ACTIVE:
            raise serializers.ValidationError(
                "Cannot add expenses to a closed trip."
            )

        if not TripMember.objects.filter(
            trip=trip,
            user=user
        ).exists():
            raise serializers.ValidationError(
                "You must be a trip member to record expenses."
            )

        if not TripMember.objects.filter(
            trip=trip,
            user=paid_by
        ).exists():
            raise serializers.ValidationError({
                "paid_by": "The payer must belong to this trip."
            })

        if data["amount"] > trip.remaining_balance:
            raise serializers.ValidationError({
                "amount": "Insufficient shared fund balance."
            })

        return data

    def create(self, validated_data):
        return Expense.objects.create(
            trip=self.context["trip"],
            recorded_by=self.context["request"].user,
            **validated_data
        )


class TripInvitationSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = TripInvitation

        fields = [
            "id",
            "trip",
            "created_by",
            "token",
            "expires_at",
            "is_active",
            "is_valid",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "trip",
            "created_by",
            "token",
            "expires_at",
            "is_active",
            "is_valid",
            "created_at",
        ]

class TripMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source="user.username",
        read_only=True
    )

    email = serializers.EmailField(
        source="user.email",
        read_only=True
    )

    class Meta:
        model = TripMember

        fields = [
            "id",
            "trip",
            "user",
            "username",
            "email",
            "role",
            "joined_at",
        ]

        read_only_fields = fields


class TripSettlementSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(
        source="member.user_id",
        read_only=True
    )

    username = serializers.CharField(
        source="member.user.username",
        read_only=True
    )

    class Meta:
        model = TripSettlement
        fields = [
            "id",
            "user_id",
            "username",
            "amount",
            "created_at"
        ]
        read_only_fields = fields


class TripTopUpShareSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(
        source="member.user_id",
        read_only=True
    )
    username = serializers.CharField(
        source="member.user.username",
        read_only=True
    )

    class Meta:
        model = TripTopUpShare
        fields = [
            "id",
            "user_id",
            "username",
            "target_amount"
        ]
        read_only_fields = fields


class TripTopUpRequestSerializer(serializers.ModelSerializer):
    shares = TripTopUpShareSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = TripTopUpRequest
        fields = [
            "id",
            "trip",
            "created_by",
            "total_amount",
            "reason",
            "status",
            "created_at",
            "shares"
        ]

        read_only_fields = [
            "id",
            "trip",
            "created_by",
            "status",
            "created_at",
            "shares"
        ]

    def validate_total_amount(self, value):
        if value <= Decimal("0.00"):
            raise serializers.ValidationError(
                "Top-up amount must be greater than zero."
            )
        return value

class TopUpContributionSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01")
    )

    note = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )