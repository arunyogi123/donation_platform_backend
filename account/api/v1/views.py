from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import extend_schema

from account.models import Profile, CreatorDocument
from account.api.v1.serialziers import (
    UserSerializer,
    ProfileSerializer,
    LoginSerializer,
    CreatorDocumentSerializer,
)

User = get_user_model()


# 🔐 REGISTER
class RegisterAPIView(APIView):

    @extend_schema(request=UserSerializer, responses=UserSerializer, tags=["Auth"])
    def post(self, request):

        serializer = UserSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            return Response(
                {
                    "message": "User registered successfully",
                    "user": UserSerializer(user).data,
                },
                status=status.HTTP_201_CREATED,
            )

        print("REGISTER ERRORS:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            email = serializer.validated_data["email"]
            password = serializer.validated_data["password"]

            user = authenticate(request, email=email, password=password)

            if user is not None:
                refresh = RefreshToken.for_user(user)

                return Response(
                    {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    }
                )

            return Response(
                {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )

        return Response(serializer.errors, status=400)


# 👤 PROFILE
class ProfileAPIView(APIView):

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(responses=ProfileSerializer, tags=["Profile"])
    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        return Response(ProfileSerializer(profile, context={"request": request}).data)

    @extend_schema(request=ProfileSerializer, responses=ProfileSerializer, tags=["Profile"])
    def put(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = ProfileSerializer(
            profile,
            data=request.data,
            partial=True,
            context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(request=ProfileSerializer, responses=ProfileSerializer, tags=["Profile"])
    def patch(self, request):
        return self.put(request)


# 📄 CREATOR DOCUMENTS
class CreatorDocumentView(APIView):

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(responses=CreatorDocumentSerializer(many=True), tags=["Profile Documents"])
    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        docs = profile.documents.all().order_by("-uploaded_at")
        serializer = CreatorDocumentSerializer(docs, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=CreatorDocumentSerializer, responses=CreatorDocumentSerializer, tags=["Profile Documents"])
    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = CreatorDocumentSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(profile=profile)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreatorDocumentDetailView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Profile Documents"])
    def delete(self, request, id):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        doc = get_object_or_404(CreatorDocument, id=id, profile=profile)
        doc.delete()
        return Response({"message": "Document removed successfully"}, status=status.HTTP_200_OK)

