import os
from rest_framework import serializers
from django.contrib.auth import get_user_model
from account.models import Profile, CreatorDocument

User = get_user_model()


import re

# 🔐 REGISTER
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    username = serializers.CharField(required=False, allow_blank=True, default="")
    full_name = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "username", "phone", "full_name"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        full_name = validated_data.pop("full_name", "")
        raw_username = validated_data.get("username", "")

        if raw_username and not full_name:
            full_name = raw_username

        if raw_username:
            clean_username = re.sub(r"[^\w.@+-]", "", raw_username)
            if clean_username:
                validated_data["username"] = clean_username
            else:
                validated_data["username"] = validated_data["email"].split("@")[0]
        else:
            validated_data["username"] = validated_data["email"].split("@")[0]

        user = User.objects.create_user(**validated_data, password=password)

        # create profile automatically with full name if provided
        Profile.objects.create(user=user, full_name=full_name or "", address="")

        return user


# 🔑 LOGIN
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


# 📄 CREATOR DOCUMENT
class CreatorDocumentSerializer(serializers.ModelSerializer):
    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)
    document_name = serializers.SerializerMethodField()
    document_url = serializers.SerializerMethodField()

    class Meta:
        model = CreatorDocument
        fields = [
            "id",
            "document",
            "document_type",
            "document_type_display",
            "document_name",
            "document_url",
            "uploaded_at",
        ]
        read_only_fields = ["uploaded_at"]

    def get_document_name(self, obj):
        if obj.document:
            return os.path.basename(obj.document.name)
        return obj.document_name or ""

    def get_document_url(self, obj):
        if not obj.document:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.document.url)
        return obj.document.url


# 👤 PROFILE
class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", required=False, allow_blank=True)
    documents = CreatorDocumentSerializer(many=True, read_only=True)
    is_creator_ready = serializers.BooleanField(read_only=True)
    missing_requirements = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
            "address",
            "bio",
            "profile_picture",
            "profile_picture_url",
            "documents",
            "is_creator_ready",
            "missing_requirements",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_profile_picture_url(self, obj):
        if not obj.profile_picture:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.profile_picture.url)
        return obj.profile_picture.url

    def get_missing_requirements(self, obj):
        return obj.get_missing_creator_requirements()

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", None)
        if user_data and "phone" in user_data:
            instance.user.phone = user_data["phone"]
            instance.user.save(update_fields=["phone"])
        return super().update(instance, validated_data)

