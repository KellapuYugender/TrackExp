
from django.contrib import admin

from .models import Trip, TripMember, Contribution, Expense, TripInvitation,TripSettlement,TripTopUpRequest, TripTopUpShare


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        "name", "currency", "status", "created_by", "created_at"
    )
    list_filter = ("status", "currency")
    search_fields = ("name", "created_by__username")


@admin.register(TripMember)
class TripMemberAdmin(admin.ModelAdmin):
    list_display = ("trip", "user", "role", "joined_at")
    list_filter = ("role",)
    search_fields = ("trip__name", "user__username")


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = (
        "trip", "member", "amount", "recorded_by", "contributed_at"
    )
    list_filter = ("contributed_at",)
    search_fields = ("trip__name", "member__user__username", "note")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "trip", "description", "amount", "category",
        "paid_by", "recorded_by", "spent_at"
    )
    list_filter = ("category", "spent_at")
    search_fields = ("trip__name", "description", "merchant")


@admin.register(TripInvitation)
class TripInvitationAdmin(admin.ModelAdmin):
    list_display = (
        "trip", "created_by", "expires_at", "is_active", "created_at"
    )
    list_filter = ("is_active",)
    search_fields = ("trip__name", "created_by__username")
    readonly_fields = ("token", "created_at")


@admin.register(TripSettlement)
class TripSettlementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "trip",
        "member",
        "amount",
        "created_at",
    )

    list_filter = ("trip", "created_at")

    search_fields = (
        "trip__name",
        "member__user__username",
    )

    readonly_fields = ("created_at",)


@admin.register(TripTopUpRequest)
class TripTopUpRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "trip",
        "total_amount",
        "status",
        "created_by",
        "created_at"
    )

    list_filter = ("status", "created_at")
    search_fields = ("trip__name",)


@admin.register(TripTopUpShare)
class TripTopUpShareAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "topup_request",
        "member",
        "target_amount"
    )

    search_fields = (
        "topup_request__trip__name",
        "member__user__username"
    )
