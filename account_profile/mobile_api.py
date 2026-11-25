from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Profile


User = get_user_model()


class MobileRegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, allow_blank=False)
    email = serializers.EmailField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Email is already registered.")
        if User.objects.filter(username__iexact=email).exists():
            raise serializers.ValidationError("Email cannot be used as a username.")
        return email

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(list(error.messages))
        return value

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data["email"]
        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=validated_data["first_name"].strip(),
            password=validated_data["password"],
        )
        Profile.objects.get_or_create(user=user)
        return user


class MobileLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class MobileProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=Profile.GENDER_CHOICES, required=False, allow_blank=True)

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.context["request"].user.pk).exists():
            raise serializers.ValidationError("Email is already in use.")
        return email


class MobileRegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = MobileRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": user_payload(user)}, status=status.HTTP_201_CREATED)


class MobileLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = MobileLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip()
        user_record = User.objects.filter(email__iexact=email).first()
        if user_record is None:
            user_record = User.objects.filter(username__iexact=email).first()
        user = None
        if user_record is not None:
            user = authenticate(request=request._request, username=user_record.username,
                                password=serializer.validated_data["password"])
        if user is None:
            return Response({"detail": "Email atau password salah."}, status=status.HTTP_400_BAD_REQUEST)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": user_payload(user)})


class MobileLogoutView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MobileProfileView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        return Response(profile_payload(request, profile))

    def patch(self, request):
        serializer = MobileProfileUpdateSerializer(data=request.data, partial=True,
                                                   context={"request": request})
        serializer.is_valid(raise_exception=True)
        profile, _ = Profile.objects.get_or_create(user=request.user)
        data = serializer.validated_data
        if "first_name" in data:
            request.user.first_name = data["first_name"].strip()
        if "email" in data:
            request.user.email = data["email"]
        if "first_name" in data or "email" in data:
            request.user.save(update_fields=[field for field in ("first_name", "email") if field in data])
        for field in ("phone_number", "date_of_birth", "gender"):
            if field in data:
                setattr(profile, field, data[field])
        profile.save()
        return Response(profile_payload(request, profile))


def user_payload(user):
    return {
        "id": user.pk,
        "username": user.username,
        "first_name": user.first_name,
        "email": user.email,
    }


def profile_payload(request, profile):
    photo_url = None
    if profile.photo:
        try:
            photo_url = request.build_absolute_uri(profile.photo.url)
        except ValueError:
            photo_url = None
    return {
        **user_payload(request.user),
        "name": request.user.first_name or request.user.username,
        "photo": photo_url,
        "date_of_birth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
        "gender": profile.gender,
        "phone_number": profile.phone_number,
    }
