from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
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
            return Response({"detail": "Your session has expired. Please sign in again."}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError):
            response = Response({"detail": "Your session has expired. Please sign in again."}, status=status.HTTP_401_UNAUTHORIZED)
            response.delete_cookie(settings.JWT_REFRESH_COOKIE_NAME, path=settings.JWT_REFRESH_COOKIE_PATH, samesite="Lax")
            return response

        return Response({"access": serializer.validated_data["access"]})


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        permission_codes = [
            "tickets.view_ticket",
            "tickets.add_ticket",
            "tickets.change_ticket",
            "tickets.delete_ticket",
        ]
        permissions = [
            code for code in permission_codes if request.user.has_perm(code)
        ]
        roles = (
            ["Admin"]
            if request.user.is_superuser
            else list(request.user.groups.values_list("name", flat=True))
        )
        role = next(
            (name for name in ("Admin", "Agent", "Viewer") if name in roles),
            "Unassigned",
        )
        return Response(
            {
                "id": request.user.pk,
                "username": request.user.get_username(),
                "role": role,
                "roles": roles,
                "permissions": permissions,
            }
        )


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
