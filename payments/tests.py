from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from payments.utils import KhaltiPayment


class KhaltiPaymentTests(SimpleTestCase):
    @override_settings(FRONTEND_URL="https://givehope.example")
    @patch("payments.utils.requests.post")
    def test_initiate_payment_uses_frontend_url_for_website_and_callback(
        self, mock_post
    ):
        response = Mock()
        response.json.return_value = {"payment_url": "https://pay.example"}
        mock_post.return_value = response

        KhaltiPayment.initiate_payment(amount=100, donation_id=1)

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["website_url"], "https://givehope.example")
        self.assertEqual(
            payload["return_url"],
            "https://givehope.example/api/payments/callback/",
        )
