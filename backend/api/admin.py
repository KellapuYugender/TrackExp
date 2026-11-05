
from django.contrib import admin

from .models import Trip, TripMember, Contribution, Expense, TripInvitation


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
