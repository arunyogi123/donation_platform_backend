from django.urls import path
from donations.api.v1.views import (
    DonationView,
    DonationUpdate,
    MyDonationsView,
    RecurringDonationView,
    RecurringManage,
    PublicDonorsView,
)

urlpatterns = [
    path("campaign-action/<int:campaign>/", DonationView.as_view(), name="see-data"),
    path("my-donations/", MyDonationsView.as_view(), name="my-donations"),
    path("donations/<int:id>/", DonationUpdate.as_view()),
    path("recurring-view", RecurringDonationView.as_view(), name="recurring-view-noslash"),
    path("recurring-view/", RecurringDonationView.as_view(), name="recurring-view"),
    path("recurring-manage/<int:id>/", RecurringManage.as_view(), name="update-delete"),
    path("public-donors/", PublicDonorsView.as_view(), name="public-donors"),
    path("public-donors", PublicDonorsView.as_view(), name="public-donors-noslash"),
]