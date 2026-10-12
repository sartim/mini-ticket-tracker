from django.urls import include, path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from tickets.auth_views import CurrentUserView, LoginView, LogoutView, RefreshView


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return Response({"status": "ok"})


urlpatterns = [
    path("health", health),
    path("auth/token", LoginView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh", RefreshView.as_view(), name="token_refresh"),
    path("auth/me", CurrentUserView.as_view(), name="current_user"),
    path("auth/logout", LogoutView.as_view(), name="logout"),
    path("", include("tickets.urls")),
]
