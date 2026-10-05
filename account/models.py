import re
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, *args, **kwargs):
        email = kwargs.pop("email", None)
        password = kwargs.pop("password", None)
        username = kwargs.pop("username", None)

        if args:
            if len(args) == 1:
                val = args[0]
                if "@" in str(val):
                    email = val
                else:
                    username = val
            elif len(args) == 2:
                if "@" in str(args[0]):
                    email = args[0]
                    password = args[1]
                else:
                    username = args[0]
                    email = args[1]
            elif len(args) >= 3:
                username = args[0]
                email = args[1]
                password = args[2]

        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)

        if not username:
            base = email.split("@")[0]
            clean = re.sub(r"[^\w.@+-]", "", base) or "user"
            candidate = clean
            counter = 1
            while self.model.objects.filter(username=candidate).exists():
                candidate = f"{clean[:130]}_{counter}"
                counter += 1
            username = candidate
        else:
            clean = re.sub(r"[^\w.@+-]", "", str(username))
            if not clean:
                clean = re.sub(r"[^\w.@+-]", "", email.split("@")[0]) or "user"
            candidate = clean
            counter = 1
            while self.model.objects.filter(username=candidate).exists():
                candidate = f"{clean[:130]}_{counter}"
                counter += 1
            username = candidate

        user = self.model(email=email, username=username, **kwargs)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractUser):
    username = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        null=True,
    )
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True)
    is_verified = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to="profiles/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name or self.user.email

    def get_missing_creator_requirements(self):
        missing = []
        if not self.profile_picture:
            missing.append("Profile Picture")
        if not self.full_name or not self.full_name.strip():
            missing.append("Full Legal Name")
        user_phone = (self.user.phone or "").strip()
        if not user_phone:
            missing.append("Contact Phone Number")
        if not self.address or not self.address.strip():
            missing.append("Address / District")
        if not self.documents.exists():
            missing.append("Verification Document")
        return missing

    @property
    def is_creator_ready(self):
        return len(self.get_missing_creator_requirements()) == 0


class CreatorDocument(models.Model):
    DOCUMENT_TYPES = [
        ("id", "Government ID / Passport / Citizenship"),
        ("address_proof", "Address Proof / Ward Recommendation"),
        ("organization", "NGO / Organization Registration"),
        ("other", "Other Supporting Document"),
    ]
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="documents")
    document = models.FileField(upload_to="creator_docs/")
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES, default="id")
    document_name = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.profile.full_name or self.profile.user.email} - {self.get_document_type_display()}"

