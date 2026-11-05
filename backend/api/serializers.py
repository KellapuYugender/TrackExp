
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from django.db import transaction
from .models import Trip, TripMember

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
