from donations.models import Donation, RecurringDonation, RecurringDonationHistory
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.generics import GenericAPIView
from donations.api.v1.serializers import (
    DonationSerializer,
    RecurringSerializer,
    PublicDonorSerializer,
)
from donations.permission import IsOwnerOrAdmin
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count, Max
from decimal import Decimal
import uuid
from receipts.models import Billing, BillingStatus, PaymentMethod
from account.models import User


class DonationView(GenericAPIView):
    queryset = Donation.objects.all()
    serializer_class = DonationSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=DonationSerializer, responses=DonationSerializer, tags=["Donation"]
    )
    def get(self, request, *args, **kwargs):


        donations = Donation.objects.filter(campaign=kwargs["campaign"])

        serializer = DonationSerializer(
            donations, many=True, context={"request": request}
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
    request=DonationSerializer, responses=DonationSerializer, tags=["Donation"]
    )
    @extend_schema(
    request=DonationSerializer, responses=DonationSerializer, tags=["Donation"]
    )
    def post(self, request, campaign):
        serializer = self.get_serializer(
            data=request.data, context={"user": request.user}
        )

        if serializer.is_valid():
            # Step 1 - Save donation as PENDING
            donation = serializer.save(
                donor=request.user,
                campaign_id=campaign,
                payment_status='PENDING'
            )

            # Step 2 - Return donation_id so frontend can initiate Khalti
            return Response({
                "message": "Donation created, proceed to payment",
                "donation_id": donation.id,
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class DonationUpdate(GenericAPIView):
    queryset = Donation.objects.all()
    serializer_class = DonationSerializer
    permission_classes = [IsAdminUser]

    @extend_schema(
        request=DonationSerializer, responses=DonationSerializer, tags=["Donation"]
    )
    def put(self, request, id):
        donation = Donation.objects.get(id=id)

        serializer = self.get_serializer(
            donation, data=request.data, context={"user": request.user}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        request=DonationSerializer, responses=DonationSerializer, tags=["Donation"]
    )
    def delete(self, request, id):
        donation = Donation.objects.get(id=id)
        donation.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class MyDonationsView(GenericAPIView):
    serializer_class = DonationSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=DonationSerializer,
        summary="Get logged-in user donations",
        tags=["Donation"],
    )
    def get(self, request):
        donations = Donation.objects.filter(donor=request.user).order_by("-created_at")
        serializer = DonationSerializer(donations, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class RecurringDonationView(GenericAPIView):
    queryset = RecurringDonation.objects.all()
    serializer_class = RecurringSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=RecurringSerializer,
        responses=RecurringSerializer,
        summary="View recurring donation",
        tags=["Recurring Donation"],
    )
    def get(self, request):
        if request.user.is_staff:
            donations = RecurringDonation.objects.all().order_by("-id")
        else:
            donations = RecurringDonation.objects.filter(donor=request.user).order_by("-id")
        serializer = RecurringSerializer(donations, many=True, context={"request": request})

        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Create recurring donation",
        tags=["Recurring Donation"],
        request=RecurringSerializer,
        responses={201: RecurringSerializer},
    )
    def post(self, request):
        serializer = RecurringSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            # Default is_active to True so it is immediately eligible for payment initiation
            is_active_val = False if request.data.get("is_active") is False or request.data.get("is_active") == "false" else True
            recurring = serializer.save(
                donor=request.user,
                is_active=is_active_val,
            )
            data = dict(serializer.data)
            data["recurring_id"] = recurring.id
            data["is_active"] = recurring.is_active
            data["message"] = "Recurring donation created, proceed to payment"
            return Response(data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class RecurringManage(GenericAPIView):
    queryset=RecurringDonation.objects.all()
    serializer_class=RecurringSerializer
    permission_classes = [IsAdminUser]
    
    @extend_schema(
        request=RecurringSerializer,
        responses=RecurringSerializer,
        tags=['Recurring Donation']
    )
    
    def put(self, request, id):
        donation = get_object_or_404(RecurringDonation, id=id)

        serializer = self.get_serializer(
            donation,
            data=request.data,
            partial=True,
            context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    @extend_schema(
        request=RecurringSerializer,
        responses=RecurringSerializer,
        tags=['Recurring Donation']
        
    )
    def delete(self, request, id):
        donation = get_object_or_404(RecurringDonation, id=id)
        donation.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicDonorsView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicDonorSerializer

    @extend_schema(
        summary="List public donors with total successful contributions",
        tags=["Donation"],
        responses={200: PublicDonorSerializer(many=True)},
    )
    def get(self, request):
        donors_map = {}

        # 1. Successful one-time public donations
        one_time_qs = (
            Donation.objects.filter(payment_status="SUCCESS", is_anonymous=False)
            .values("donor")
            .annotate(
                total=Sum("amount"),
                count=Count("id"),
                last=Max("created_at"),
            )
        )
        for row in one_time_qs:
            d_id = row["donor"]
            if d_id:
                donors_map[d_id] = {
                    "total": row["total"] or Decimal("0"),
                    "count": row["count"],
                    "last": row["last"],
                }

        # 2. Successful recurring donation history (where recurring_donation is not anonymous)
        recurring_qs = (
            RecurringDonationHistory.objects.filter(
                payment_status="SUCCESS",
                recurring_donation__is_anonymous=False,
            )
            .values("donor")
            .annotate(
                total=Sum("amount"),
                count=Count("id"),
                last=Max("paid_at"),
            )
        )
        for row in recurring_qs:
            d_id = row["donor"]
            if d_id:
                if d_id in donors_map:
                    donors_map[d_id]["total"] += row["total"] or Decimal("0")
                    donors_map[d_id]["count"] += row["count"]
                    if row["last"] and (
                        not donors_map[d_id]["last"] or row["last"] > donors_map[d_id]["last"]
                    ):
                        donors_map[d_id]["last"] = row["last"]
                else:
                    donors_map[d_id] = {
                        "total": row["total"] or Decimal("0"),
                        "count": row["count"],
                        "last": row["last"],
                    }

        if not donors_map:
            return Response([], status=status.HTTP_200_OK)

        users = User.objects.filter(id__in=donors_map.keys()).select_related("profile")
        results = []
        for user in users:
            stats = donors_map.get(user.id, {})
            profile = getattr(user, "profile", None)
            profile_pic = None
            if profile and profile.profile_picture:
                try:
                    profile_pic = (
                        request.build_absolute_uri(profile.profile_picture.url)
                        if request
                        else profile.profile_picture.url
                    )
                except Exception:
                    profile_pic = profile.profile_picture.url

            # Public username only - never expose email or phone
            username = user.username or (profile.full_name if profile else f"donor_{user.id}")
            if "@" in username:
                username = username.split("@")[0]

            results.append({
                "id": user.id,
                "username": username,
                "full_name": profile.full_name if profile else "",
                "profile_picture": profile_pic,
                "total_donated": stats.get("total", Decimal("0")),
                "currency": "NPR",
                "donation_count": stats.get("count", 1),
                "last_donated": stats.get("last"),
            })

        # Sort highest total donated first
        results.sort(key=lambda x: x["total_donated"], reverse=True)
        serializer = PublicDonorSerializer(results, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)