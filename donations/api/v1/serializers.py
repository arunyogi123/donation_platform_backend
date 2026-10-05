from rest_framework import serializers
from donations.models import Donation, RecurringDonation


# =========================
# 🔁 RECURRING DONATION
# =========================
class RecurringSerializer(serializers.ModelSerializer):
    campaign_title = serializers.CharField(
        source="campaign.title",
        read_only=True
    )
    is_active = serializers.BooleanField(default=True, required=False)

    class Meta:
        model = RecurringDonation
        fields = "__all__"

        read_only_fields = [
            "donor",
            "next_run",
            "last_run",
            "is_processing",
            "last_payment_status",
            "created_at",
            "updated_at",
        ]


    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")

        # Hide donor for non-staff + anonymous users
        if request and not request.user.is_staff:
            if instance.is_anonymous:
                data["donor"] = "***"

        return data


# =========================
# 💳 DONATION (ONE-TIME)
# =========================
class DonationSerializer(serializers.ModelSerializer):

    recurring = RecurringSerializer(read_only=True)

    campaign = serializers.CharField(
        source="campaign.title",
        read_only=True
    )

    class Meta:
        model = Donation
        fields = "__all__"

        read_only_fields = [
            "donor",
            "payment_status",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")

        # Hide donor for anonymous donations (unless admin)
        if request and not request.user.is_staff:
            if instance.is_anonymous:
                data["donor"] = "***"

        return data