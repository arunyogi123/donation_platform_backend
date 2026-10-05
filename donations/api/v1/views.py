from donations.models import Donation, RecurringDonation
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.generics import GenericAPIView
from donations.api.v1.serializers import DonationSerializer, RecurringSerializer
from rest_framework.permissions import IsAuthenticated
from donations.permission import IsOwnerOrAdmin
from django.utils import timezone
from django.shortcuts import get_object_or_404
import uuid
from receipts.models import Billing,BillingStatus,PaymentMethod


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