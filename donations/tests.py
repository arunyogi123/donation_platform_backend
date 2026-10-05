from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status

from account.models import Profile, CreatorDocument
from campaign.models import Campaign, CategoryType
from donations.models import Donation, RecurringDonation, RecurringDonationHistory, PaymentType, RecurringType
from receipts.models import Billing, BillingStatus, PaymentMethod

User = get_user_model()

TINY_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
    b"\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00"
    b"\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


class GiveHopeIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.donor_user = User.objects.create_user(
            username="testdonor",
            email="donor@example.com",
            password="Password123!",
            first_name="Test",
            last_name="Donor",
            phone="9800000001",
        )
        self.creator_user = User.objects.create_user(
            username="testcreator",
            email="creator@example.com",
            password="Password123!",
            first_name="Test",
            last_name="Creator",
            phone="9800000002",
        )
        self.campaign = Campaign.objects.create(
            user=self.creator_user,
            title="Urgent Medical Care for Children",
            description="Helping children receive critical cardiac procedures.",
            category=CategoryType.HEALTH,
            goal_amount=500000,
            current_raised=0,
            is_approved=True,
            is_active=True,
        )

    def test_creator_profile_requirements_detection(self):
        self.creator_user.phone = ""
        self.creator_user.save()
        profile = getattr(self.creator_user, "profile", None)
        if not profile:
            profile = Profile.objects.create(user=self.creator_user)

        # Profile starts incomplete
        profile.full_name = ""
        profile.phone = ""
        profile.address = ""
        profile.profile_picture = None
        profile.save()

        missing = profile.get_missing_creator_requirements()
        self.assertIn("Profile Picture", missing)
        self.assertIn("Full Legal Name", missing)
        self.assertIn("Contact Phone Number", missing)
        self.assertIn("Address / District", missing)
        self.assertIn("Verification Document", missing)
        self.assertFalse(profile.is_creator_ready)

        # Adding partial info
        profile.full_name = "Test Creator Legal"
        self.creator_user.phone = "9812345678"
        self.creator_user.save()
        profile.phone = "9812345678"
        profile.address = "Kathmandu, Nepal"
        profile.profile_picture = SimpleUploadedFile("avatar.gif", TINY_GIF, content_type="image/gif")
        profile.save()

        missing = profile.get_missing_creator_requirements()
        self.assertEqual(len(missing), 1)
        self.assertIn("Verification Document", missing)
        self.assertFalse(profile.is_creator_ready)

        # Upload document
        CreatorDocument.objects.create(
            profile=profile,
            document_type="id",
            document=SimpleUploadedFile("citizenship.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        )
        self.assertTrue(profile.is_creator_ready)
        self.assertEqual(len(profile.get_missing_creator_requirements()), 0)

    def test_campaign_creation_enforces_creator_ready_and_documents(self):
        self.client.force_authenticate(user=self.creator_user)
        profile = getattr(self.creator_user, "profile", None)
        if not profile:
            profile = Profile.objects.create(user=self.creator_user)

        # Incomplete profile blocked
        profile.full_name = ""
        profile.save()
        response = self.client.post("/api/campaign/campaign-action/", {
            "title": "New Initiative",
            "description": "Story of appeal",
            "category": "HEALTH",
            "goal_amount": 100000,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("missing_requirements", response.data)

        # Complete profile
        profile.full_name = "Verified Creator"
        self.creator_user.phone = "9800000000"
        self.creator_user.save()
        profile.phone = "9800000000"
        profile.address = "Lalitpur"
        profile.profile_picture = SimpleUploadedFile("avatar.gif", TINY_GIF, content_type="image/gif")
        profile.save()
        CreatorDocument.objects.create(
            profile=profile,
            document_type="id",
            document=SimpleUploadedFile("id.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        )

        # Missing campaign cover photo
        response = self.client.post("/api/campaign/campaign-action/", {
            "title": "Hospital Wing Repair",
            "description": "Critical rebuilding project.",
            "category": "HEALTH",
            "goal_amount": 100000,
            "document": SimpleUploadedFile("estimate.pdf", b"%PDF-1.4 estimate", content_type="application/pdf"),
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Please upload a campaign cover photograph", response.data.get("detail", ""))

        # Missing campaign case document
        response = self.client.post("/api/campaign/campaign-action/", {
            "title": "Hospital Wing Repair",
            "description": "Critical rebuilding project.",
            "category": "HEALTH",
            "goal_amount": 100000,
            "image": SimpleUploadedFile("cover.jpg", TINY_GIF, content_type="image/jpeg"),
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Please upload at least one supporting document", response.data.get("detail", ""))

        # Complete campaign submission succeeds
        response = self.client.post("/api/campaign/campaign-action/", {
            "title": "Hospital Wing Repair",
            "description": "Critical rebuilding project with official documents attached.",
            "category": "HEALTH",
            "goal_amount": 100000,
            "image": SimpleUploadedFile("cover.jpg", TINY_GIF, content_type="image/jpeg"),
            "document": SimpleUploadedFile("estimate.pdf", b"%PDF-1.4 estimate", content_type="application/pdf"),
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch("payments.utils.KhaltiPayment.verify_payment")
    def test_one_time_donation_flow_creates_only_donation(self, mock_verify):
        mock_verify.return_value = {"status": "Completed"}
        self.client.force_authenticate(user=self.donor_user)

        # 1. Create One-Time Donation
        create_res = self.client.post(f"/api/donations/campaign-action/{self.campaign.id}/", {
            "amount": "2500.00",
            "currency": "NPR",
            "is_anonymous": False,
        })
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        donation_id = create_res.data["donation_id"]

        donation = Donation.objects.get(id=donation_id)
        self.assertEqual(donation.payment_status, PaymentType.PENDING)
        self.assertEqual(donation.amount, 2500)

        # 2. Payment callback
        callback_res = self.client.get(
            f"/api/payments/callback/?pidx=TXN_ONETIME_123&purchase_order_id={donation_id}&status=Completed"
        )
        self.assertEqual(callback_res.status_code, 200)

        # 3. Verify database state
        donation.refresh_from_db()
        self.assertEqual(donation.payment_status, PaymentType.SUCCESS)

        # Must have created Billing with is_recurring=False
        billing = Billing.objects.get(transaction_id="TXN_ONETIME_123")
        self.assertEqual(billing.donation, donation)
        self.assertIsNone(billing.recurring_donation)
        self.assertFalse(billing.is_recurring)
        self.assertEqual(billing.status, BillingStatus.SUCCESS)

        # Must NOT have created any RecurringDonation or RecurringDonationHistory
        self.assertEqual(RecurringDonation.objects.count(), 0)
        self.assertEqual(RecurringDonationHistory.objects.count(), 0)

        # Campaign current_raised incremented
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.current_raised, 2500)

        # Check My Donations endpoint returns this donation
        my_res = self.client.get("/api/donations/my-donations/")
        self.assertEqual(my_res.status_code, 200)
        self.assertEqual(len(my_res.data), 1)
        self.assertEqual(my_res.data[0]["id"], donation.id)

    @override_settings(FRONTEND_URL="https://givehope.example")
    @patch("payments.utils.KhaltiPayment.verify_payment")
    @patch("payments.utils.KhaltiPayment.initiate_payment")
    def test_recurring_donation_flow_creates_only_recurring_donation(self, mock_init, mock_verify):
        mock_init.return_value = {"payment_url": "https://test-pay.khalti.com/?pidx=TXN_RECURRING_456"}
        mock_verify.return_value = {"status": "Completed"}
        self.client.force_authenticate(user=self.donor_user)

        # Initial donations count
        initial_one_time_count = Donation.objects.count()

        # 1. Create Recurring Donation
        recurring_res = self.client.post("/api/donations/recurring-view/", {
            "campaign": self.campaign.id,
            "amount": "1500.00",
            "currency": "NPR",
            "recurring_timing": RecurringType.MONTHLY,
            "is_anonymous": False,
        })
        self.assertEqual(recurring_res.status_code, status.HTTP_201_CREATED)
        recurring_id = recurring_res.data["recurring_id"]

        plan = RecurringDonation.objects.get(id=recurring_id)
        # Should be active by default for immediate payment
        self.assertTrue(plan.is_active)
        self.assertEqual(plan.last_payment_status, PaymentType.PENDING)

        # 2. Initiate Recurring Payment Gateway
        init_res = self.client.get(f"/api/payments/recurring/{plan.id}/")
        self.assertEqual(init_res.status_code, 200)
        self.assertIn("payment_url", init_res.data)
        self.assertEqual(
            mock_init.call_args.kwargs["return_url"],
            "https://givehope.example/api/payments/recurring/callback/",
        )

        # 3. Recurring Payment Callback
        callback_res = self.client.get(
            f"/api/payments/recurring/callback/?pidx=TXN_RECURRING_456&purchase_order_id={plan.id}&status=Completed"
        )
        self.assertEqual(callback_res.status_code, 200)

        # 4. Verify RecurringDonation updated
        plan.refresh_from_db()
        self.assertEqual(plan.last_payment_status, PaymentType.SUCCESS)
        self.assertFalse(plan.is_processing)

        # Must have created Billing with recurring_donation=plan, donation=None, is_recurring=True
        billing = Billing.objects.get(transaction_id="TXN_RECURRING_456")
        self.assertIsNone(billing.donation)
        self.assertEqual(billing.recurring_donation, plan)
        self.assertTrue(billing.is_recurring)
        self.assertEqual(billing.status, BillingStatus.SUCCESS)

        # Must have created RecurringDonationHistory
        history = RecurringDonationHistory.objects.get(recurring_donation=plan)
        self.assertEqual(history.payment_status, PaymentType.SUCCESS)
        self.assertEqual(history.amount, 1500)

        # CRITICAL RULE: Must NOT create any record in normal Donation table!
        self.assertEqual(Donation.objects.count(), initial_one_time_count)

        # Campaign current_raised incremented
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.current_raised, 1500)

        # My Donations endpoint must NOT contain the recurring donation
        my_donations_res = self.client.get("/api/donations/my-donations/")
        self.assertEqual(my_donations_res.status_code, 200)
        self.assertEqual(len(my_donations_res.data), initial_one_time_count)

        # Recurring Donations endpoint must contain this plan
        my_recurring_res = self.client.get("/api/donations/recurring-view/")
        self.assertEqual(my_recurring_res.status_code, 200)
        self.assertEqual(len(my_recurring_res.data), 1)
        self.assertEqual(my_recurring_res.data[0]["id"], plan.id)

    def test_registration_without_username_and_with_spaces_in_name(self):
        # 1. Register with email and password only (no username sent)
        res1 = self.client.post("/api/account/register/", {
            "email": "nousername@example.com",
            "password": "Password123!",
            "phone": "9811111111",
        })
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        user1 = User.objects.get(email="nousername@example.com")
        self.assertTrue(user1.username)
        self.assertEqual(user1.email, "nousername@example.com")
        self.assertTrue(hasattr(user1, "profile"))

        # 2. Register with full name containing spaces in username field (e.g. "Aarav Sharma")
        res2 = self.client.post("/api/account/register/", {
            "username": "Aarav Sharma",
            "email": "aarav@example.com",
            "password": "Password123!",
            "phone": "9822222222",
        })
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        user2 = User.objects.get(email="aarav@example.com")
        self.assertEqual(user2.profile.full_name, "Aarav Sharma")
        # System username should be valid without spaces
        self.assertNotIn(" ", user2.username)
