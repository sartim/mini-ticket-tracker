from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            refresh_token = response.data.pop("refresh", None)
            access_token = response.data.get("access")
            user_id = AccessToken(access_token)[
                settings.SIMPLE_JWT.get("USER_ID_CLAIM", "user_id")
            ]
            user = get_user_model().objects.get(pk=user_id)
            response.data["user"] = serialize_user(user)
            if refresh_token:
                response.set_cookie(
                    settings.JWT_REFRESH_COOKIE_NAME,
                    refresh_token,
                    httponly=True,
                    secure=settings.JWT_REFRESH_COOKIE_SECURE,
                    samesite="Lax",
                    path=settings.JWT_REFRESH_COOKIE_PATH,
                    max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
                )
        return response


class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if not refresh_token:
            return Response(
                {"error": "Your session has expired. Please sign in again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError):
            response = Response(
                {"error": "Your session has expired. Please sign in again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            response.delete_cookie(
                settings.JWT_REFRESH_COOKIE_NAME,
                path=settings.JWT_REFRESH_COOKIE_PATH,
                samesite="Lax",
            )
            return response

        access = serializer.validated_data["access"]
        user_id = AccessToken(access)[
            settings.SIMPLE_JWT.get("USER_ID_CLAIM", "user_id")
        ]
        user = get_user_model().objects.get(pk=user_id)
        return Response({"access": access, "user": serialize_user(user)})


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(serialize_user(request.user))


def serialize_user(user):
    role_names = (
        ["Admin"]
        if user.is_superuser
        else list(user.groups.values_list("name", flat=True))
    )
    role = next(
        (name for name in ("Admin", "Agent", "Viewer") if name in role_names),
        "Unassigned",
    )
    available_permissions = Permission.objects.filter(
        content_type__app_label="tickets",
        codename__in=("view_ticket", "add_ticket", "change_ticket", "delete_ticket"),
    ).order_by("codename")
    granted = {
        permission.codename
        for permission in available_permissions
        if user.has_perm(f"tickets.{permission.codename}")
    }
    return {
        "id": user.pk,
        "username": user.get_username(),
        "role": role,
        "roles": [{"name": name} for name in role_names],
        "permissions": [
            {"code": f"tickets.{permission.codename}", "name": permission.name}
            for permission in available_permissions
            if permission.codename in granted
        ],
    }


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw_refresh_token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if raw_refresh_token:
            try:
                RefreshToken(raw_refresh_token).blacklist()
            except (TokenError, TypeError, AttributeError):
                pass
        response = Response(status=status.HTTP_205_RESET_CONTENT)
        response.delete_cookie(settings.JWT_REFRESH_COOKIE_NAME, path=settings.JWT_REFRESH_COOKIE_PATH, samesite="Lax")
        return response
