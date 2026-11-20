
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Trip, TripMember, TripSettlement

User = get_user_model()


class TrackExpTests(APITestCase):

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="test_admin",
            password="TestPassword123!"
        )

        self.friend_user = User.objects.create_user(
            username="test_friend",
            password="TestPassword123!"
        )

        self.trip = Trip.objects.create(
            name="Automated Test Trip",
            description="Testing TrackExp backend",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
            currency="CAD",
            created_by=self.admin_user
        )

        self.admin_member = TripMember.objects.create(
            trip=self.trip,
            user=self.admin_user,
            role=TripMember.Role.ADMIN
        )

        self.friend_member = TripMember.objects.create(
            trip=self.trip,
            user=self.friend_user,
            role=TripMember.Role.MEMBER
        )

        self.client.force_authenticate(user=self.admin_user)

        self.contributions_url = (
            f"/api/trips/{self.trip.id}/contributions/"
        )
        self.expenses_url = (
            f"/api/trips/{self.trip.id}/expenses/"
        )
        self.close_url = (
            f"/api/trips/{self.trip.id}/close/"
        )

    def add_contribution(self, amount):
        return self.client.post(
            self.contributions_url,
            {
                "member": self.admin_member.id,
                "amount": amount,
                "note": "Test contribution"
            },
            format="json"
        )

    def test_positive_contribution(self):
        response = self.add_contribution("100.00")

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertEqual(
            self.trip.remaining_balance,
            Decimal("100.00")
        )

    def test_negative_contribution_rejected(self):
        response = self.add_contribution("-50.00")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(
            self.trip.remaining_balance,
            Decimal("0.00")
        )

    def test_insufficient_balance_rejected(self):
        self.add_contribution("100.00")

        response = self.client.post(
            self.expenses_url,
            {
                "paid_by": self.admin_user.id,
                "amount": "150.00",
                "merchant": "Test Store",
                "category": "OTHER"
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(
            self.trip.remaining_balance,
            Decimal("100.00")
        )

    def test_trip_closure_creates_settlements(self):
        self.add_contribution("100.00")

        response = self.client.post(
            self.close_url,
            {},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.trip.refresh_from_db()

        self.assertEqual(
            self.trip.status,
            Trip.Status.CLOSED
        )

        settlements = TripSettlement.objects.filter(
            trip=self.trip
        )

        self.assertEqual(settlements.count(), 2)

        for settlement in settlements:
            self.assertEqual(
                settlement.amount,
                Decimal("50.00")
            )

        self.assertEqual(
            sum(s.amount for s in settlements),
            Decimal("100.00")
        )
    
    def test_closed_trip_rejects_contributions_and_expenses(self):
        self.add_contribution("100.00")

        close_response = self.client.post(
            self.close_url, {}, format="json"
        )
        self.assertEqual(close_response.status_code, 200)

        contribution_response = self.add_contribution("50.00")

        expense_response = self.client.post(
            self.expenses_url,
            {
                "paid_by": self.admin_user.id,
                "amount": "20.00",
                "merchant": "Test Store",
                "category": "OTHER"
            },
            format="json"
        )

        self.assertEqual(contribution_response.status_code, 400)
        self.assertEqual(expense_response.status_code, 400)


    def test_non_member_cannot_view_settlements(self):
        outsider = User.objects.create_user(
            username="outsider",
            password="TestPassword123!"
        )

        self.client.force_authenticate(user=outsider)

        response = self.client.get(
            f"/api/trips/{self.trip.id}/settlements/"
        )

        self.assertEqual(response.status_code, 404)
