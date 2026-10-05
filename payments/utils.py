import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class KhaltiPayment:

    @staticmethod
    def initiate_payment(**data):
        if not settings.FRONTEND_URL:
            raise ImproperlyConfigured(
                "Set FRONTEND_URL in the environment or backend/.env before initiating payments."
            )

        payload = {
            "return_url": data.get(
                "return_url",
                f"{settings.FRONTEND_URL}/api/payments/callback/",
            ),
            "website_url": settings.FRONTEND_URL,
            "amount": int(float(data.get("amount"))) * 100,
            "purchase_order_id": str(data.get("donation_id")),
            "purchase_order_name": "Donation Payment",
            "customer_info": {
                "name": data.get("name"),
                "email": data.get("email"),
                "phone": data.get("phone"),
            }
        }

        headers = {
            "Authorization": f"key {settings.KHALTI_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            settings.KHALTI_INIT_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def verify_payment(pidx):
        headers = {
            "Authorization": f"key {settings.KHALTI_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            settings.KHALTI_VERIFY_URL,
            json={"pidx": pidx},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()