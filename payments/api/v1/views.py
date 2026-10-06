import requests
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from campaign.models import Campaign
from django.db.models import F
from receipts.models import Billing, BillingStatus, PaymentMethod
from donations.models import Donation, RecurringDonation, PaymentType
from payments.utils import KhaltiPayment


# ── ONE TIME DONATION ──────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def initiate_donation(request, donation_id):
    donation = get_object_or_404(Donation, id=donation_id, donor=request.user)

    if donation.payment_status == PaymentType.SUCCESS:
        return Response({"error": "Already paid"}, status=400)

    data = KhaltiPayment.initiate_payment(
        amount=donation.amount,
        donation_id=donation.id,
        name=request.user.username,
        email=request.user.email,
        phone=getattr(request.user, "phone", "9800000000"),
    )

    return Response({"payment_url": data.get("payment_url")})


@api_view(["GET"])
def donation_callback(request):
    pidx = request.GET.get("pidx")
    donation_id = request.GET.get("purchase_order_id")
    status_param = request.GET.get("status")

    donation = get_object_or_404(Donation, id=donation_id)

    context = {
        "transaction_id": pidx,
        "amount": donation.amount,
        "frontend_url": settings.FRONTEND_URL,
    }

    if Billing.objects.filter(transaction_id=pidx).exists():
        return render(request, "payment/index.html", {**context, "status": "success"})

    if status_param and status_param.lower() == "user canceled":
        donation.payment_status = PaymentType.FAILURE
        donation.save()
        return render(request, "payment/index.html", {**context, "status": "cancelled"})

    response = KhaltiPayment.verify_payment(pidx)

    if response.get("status") == "Completed":
        donation.payment_status = PaymentType.SUCCESS
        donation.save()
        Billing.objects.create(
            donation=donation,
            transaction_id=pidx,
            amount=donation.amount,
            currency=donation.currency,
            status=BillingStatus.SUCCESS,
            payment_method=PaymentMethod.KHALTI,
            is_recurring=False,
        )
        return render(request, "payment/index.html", {**context, "status": "success"})

    donation.payment_status = PaymentType.FAILURE
    donation.save()
    return render(request, "payment/index.html", {**context, "status": "failed"})


# ── RECURRING DONATION ─────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def initiate_recurring(request, recurring_id):
    plan = get_object_or_404(RecurringDonation, id=recurring_id, donor=request.user)

    if not plan.is_active:
        plan.is_active = True
        plan.save(update_fields=["is_active"])

    plan.is_processing = True
    plan.save(update_fields=["is_processing"])

    phone_num = getattr(request.user, "phone", None) or "9800000000"

    try:
        data = KhaltiPayment.initiate_payment(
            amount=plan.amount,
            donation_id=plan.id,
            return_url=f"{settings.FRONTEND_URL}/api/payments/recurring/callback/",
            name=request.user.username or "GiveHope Donor",
            email=request.user.email,
            phone=phone_num,
        )
        return Response({"payment_url": data.get("payment_url")})
    except Exception as exc:
        plan.is_processing = False
        plan.save(update_fields=["is_processing"])
        return Response(
            {"error": f"Failed to initialize payment gateway: {str(exc)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )


@api_view(["GET"])
def recurring_callback(request):
    pidx = request.GET.get("pidx")
    recurring_id = request.GET.get("purchase_order_id")
    status_param = request.GET.get("status")

    plan = get_object_or_404(RecurringDonation, id=recurring_id)

    context = {
        "transaction_id": pidx,
        "amount": plan.amount,
        "recurring_id": plan.id,
        "frontend_url": settings.FRONTEND_URL,
    }

    if Billing.objects.filter(transaction_id=pidx).exists():
        return render(request, "payment/index.html", {**context, "status": "success"})

    if status_param and status_param.lower() == "user canceled":
        plan.last_payment_status = PaymentType.FAILURE
        plan.is_processing = False
        plan.save()
        return render(request, "payment/index.html", {**context, "status": "cancelled"})

    response = KhaltiPayment.verify_payment(pidx)

    if response.get("status") == "Completed":
        Billing.objects.create(
            donation=None,
            recurring_donation=plan,
            transaction_id=pidx,
            amount=plan.amount,
            currency=plan.currency,
            status=BillingStatus.SUCCESS,
            payment_method=PaymentMethod.KHALTI,
            is_recurring=True,
        )
        Campaign.objects.filter(pk=plan.campaign_id).update(
            current_raised=F("current_raised") + plan.amount
        )
        plan.mark_success()
        return render(request, "payment/index.html", {**context, "status": "success"})

    plan.mark_failure()
    return render(request, "payment/index.html", {**context, "status": "failed"})
