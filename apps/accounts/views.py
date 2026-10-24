from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Count
from django.middleware.csrf import get_token
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsStaffUser

from .models import Address, Favorite, User
from .serializers import (
    AddressSerializer, AdminCustomerSerializer, ChangePasswordSerializer, FavoriteSerializer, LoginSerializer,
    PasswordResetConfirmSerializer, PasswordResetSerializer, RegisterSerializer, UserSerializer,
)


class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class ScopedAPIView(APIView):
    throttle_scope = None


class RegisterView(ScopedAPIView):
    permission_classes = [AllowAny]
    throttle_scope = "register"

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(ScopedAPIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        s = LoginSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        login(request, s.validated_data["user"])
        return Response(UserSerializer(s.validated_data["user"]).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(ScopedAPIView):
    """Changement de mot de passe pour un utilisateur connecté.

    Throttle "change_password" (5/hour) pour limiter le brute-force
    du mot de passe actuel par un attaquant ayant accès à la session.
    Le re-login() après set_password maintient la session valide.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "change_password"

    def post(self, request):
        s = ChangePasswordSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        if not request.user.check_password(s.validated_data["current_password"]):
            return Response(
                {"detail": "Mot de passe actuel incorrect.", "errors": {"current_password": ["Mot de passe actuel incorrect."]}},
                status=400,
            )
        request.user.set_password(s.validated_data["new_password"])
        request.user.save()
        login(request, request.user, backend="django.contrib.auth.backends.ModelBackend")
        return Response({"detail": "Mot de passe mis a jour."})


class PasswordResetView(ScopedAPIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    def post(self, request):
        s = PasswordResetSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = User.objects.filter(email=s.validated_data["email"].lower(), is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.FRONTEND_URL}/reinitialiser-mot-de-passe?uid={uid}&token={token}"
            send_mail(
                "Reinitialisation de votre mot de passe",
                f"Bonjour,\n\nPour choisir un nouveau mot de passe, ouvrez ce lien :\n{link}\n\n"
                "Si vous n'etes pas a l'origine de cette demande, ignorez ce message.",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
            )
        # Reponse identique que le compte existe ou non (pas d'enumeration).
        return Response({"detail": "Si un compte existe avec cet e-mail, un message vient d'etre envoye."})


class PasswordResetConfirmView(ScopedAPIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    def post(self, request):
        s = PasswordResetConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(s.validated_data["uid"])))
        except Exception:
            user = None
        if not user or not default_token_generator.check_token(user, s.validated_data["token"]):
            return Response({"detail": "Lien invalide ou expire.", "errors": {}}, status=400)
        user.set_password(s.validated_data["password"])
        user.save()
        return Response({"detail": "Mot de passe mis a jour. Vous pouvez vous connecter."})


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user).select_related("delivery_zone")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class FavoriteViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    lookup_field = "product_id"

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related("product__category").prefetch_related("product__images")

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        fav, _ = Favorite.objects.get_or_create(user=request.user, product_id=s.validated_data["product_id"])
        return Response(self.get_serializer(fav).data, status=201)


class AdminCustomerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AdminCustomerSerializer
    permission_classes = [IsStaffUser]
    search_fields = ["email", "first_name", "last_name", "phone"]
    ordering = ["-date_joined"]

    def get_queryset(self):
        return User.objects.filter(is_staff=False).annotate(orders_count=Count("orders"))
