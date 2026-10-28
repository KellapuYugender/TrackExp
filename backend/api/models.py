
from datetime import timedelta
from decimal import Decimal, ROUND_DOWN
from secrets import token_urlsafe

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone


class Trip(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CLOSED = "CLOSED", "Closed"

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    currency = models.CharField(max_length=3, default="CAD")
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_trips",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["ACTIVE", "CLOSED"]),
                name="valid_trip_status",
            ),
        ]

    def clean(self):
        super().clean()

        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError({
                    "end_date": "End date cannot be before start date."
                })

        if self.status == self.Status.CLOSED and not self.closed_at:
            raise ValidationError({
                "closed_at": "A closed trip must have a closure timestamp."
            })

        if self.status == self.Status.ACTIVE and self.closed_at:
            raise ValidationError({
                "closed_at": "An active trip cannot have a closure timestamp."
            })

    @property
    def total_contributions(self):
        result = self.contributions.aggregate(total=Sum("amount"))
        return result["total"] or Decimal("0.00")

    @property
    def total_expenses(self):
        result = self.expenses.aggregate(total=Sum("amount"))
        return result["total"] or Decimal("0.00")

    @property
    def remaining_balance(self):
        return self.total_contributions - self.total_expenses

    @property
    def equal_share_estimate(self):
        count = self.members.count()

        if count == 0:
            return Decimal("0.00")

        # Rounded down to cents. Closure logic must allocate any
        # leftover cents fairly when recording final settlements.
        return (self.remaining_balance / count).quantize(
            Decimal("0.01"),
            rounding=ROUND_DOWN,
        )

    def __str__(self):
        return self.name


class TripMember(models.Model):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        MEMBER = "MEMBER", "Member"

    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="trip_memberships",
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["trip", "user"],
                name="unique_user_per_trip",
            ),
        ]

    def clean(self):
        super().clean()

        if self.trip_id and self.trip.status != Trip.Status.ACTIVE:
            # Existing members remain visible after closure, but
            # adding new members to a closed trip is not allowed.
            if self._state.adding:
                raise ValidationError(
                    "Cannot add a member to a closed trip."
                )

    def __str__(self):
        return f"{self.user} - {self.trip}"


class Contribution(models.Model):
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="contributions",
    )
    member = models.ForeignKey(
        TripMember,
        on_delete=models.PROTECT,
        related_name="contributions",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_contributions",
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    contributed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-contributed_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="contribution_amount_positive",
            ),
        ]

    def clean(self):
        super().clean()

        if self.member_id and self.trip_id:
            if self.member.trip_id != self.trip_id:
                raise ValidationError(
                    "The contributing member must belong to this trip."
                )

        if self.trip_id and self.trip.status != Trip.Status.ACTIVE:
            raise ValidationError(
                "Contributions cannot be recorded for a closed trip."
            )

        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Amount must be positive."})

    def __str__(self):
        return f"{self.trip} - {self.amount}"


class Expense(models.Model):
    class Category(models.TextChoices):
        FOOD = "FOOD", "Food"
        TRANSPORT = "TRANSPORT", "Transport"
        ACCOMMODATION = "ACCOMMODATION", "Accommodation"
        ACTIVITIES = "ACTIVITIES", "Activities"
        SHOPPING = "SHOPPING", "Shopping"
        OTHER = "OTHER", "Other"

    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="paid_trip_expenses",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_trip_expenses",
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    merchant = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )

    spent_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-spent_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="expense_amount_positive",
            ),
        ]

    def clean(self):
        super().clean()

        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Amount must be positive."})

        if self.trip_id:
            if self.trip.status != Trip.Status.ACTIVE:
                raise ValidationError(
                    "Expenses cannot be recorded for a closed trip."
                )

            # Both the payer and the person recording the expense
            # must be members of this trip.
            if self.paid_by_id and not TripMember.objects.filter(
                trip_id=self.trip_id, user_id=self.paid_by_id
            ).exists():
                raise ValidationError({
                    "paid_by": "The payer must be a member of this trip."
                })

            if self.recorded_by_id and not TripMember.objects.filter(
                trip_id=self.trip_id, user_id=self.recorded_by_id
            ).exists():
                raise ValidationError({
                    "recorded_by": "The recorder must be a member of this trip."
                })

    def __str__(self):
        return f"{self.description} - {self.amount}"


class TripInvitation(models.Model):
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_trip_invitations",
    )

    token = models.CharField(
        max_length=64,
        unique=True,
        default=token_urlsafe,
        editable=False,
    )
    expires_at = models.DateTimeField(
        default=lambda: timezone.now() + timedelta(days=7)
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_valid(self):
        return (
            self.is_active
            and self.trip.status == Trip.Status.ACTIVE
            and timezone.now() < self.expires_at
        )

    def clean(self):
        super().clean()

        if self.trip_id and self.trip.status != Trip.Status.ACTIVE:
            raise ValidationError(
                "Invitations cannot be created for a closed trip."
            )

        if self.expires_at and self.expires_at <= timezone.now():
            raise ValidationError({
                "expires_at": "Invitation expiry must be in the future."
            })

        if self.trip_id and self.created_by_id:
            if not TripMember.objects.filter(
                trip_id=self.trip_id,
                user_id=self.created_by_id,
            ).exists():
                raise ValidationError(
                    "Only a trip member can create an invitation."
                )

    def __str__(self):
        return f"Invitation for {self.trip}"
