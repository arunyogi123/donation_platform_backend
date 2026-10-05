from django.urls import path
from .views import (
    RegisterAPIView,
    ProfileAPIView,
    LoginView,
    CreatorDocumentView,
    CreatorDocumentDetailView,
)

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name="create-account"),
    path('profile/', ProfileAPIView.as_view(), name="check-profile"),
    path('profile/documents/', CreatorDocumentView.as_view(), name="creator-documents"),
    path('profile/documents/<int:id>/', CreatorDocumentDetailView.as_view(), name="creator-document-detail"),
    path("login/", LoginView.as_view(), name="login-account"),
]