from django.urls import include, path
from django.http import JsonResponse
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


def api_not_found(request, exception):
    if request.path.startswith("/api/v1/"):
        return JsonResponse({"error": "Not found."}, status=404)
    from django.views.defaults import page_not_found

    return page_not_found(request, exception)


urlpatterns = []
urlpatterns.append(path("api/v1/session-auth/", include("rest_framework.urls")))

urlpatterns += [
    path("api/v1/health", health),
    path("api/v1/auth/token", LoginView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh", RefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/me", CurrentUserView.as_view(), name="current_user"),
    path("api/v1/auth/logout", LogoutView.as_view(), name="logout"),
    path("api/v1/", include("tickets.urls")),
]

handler404 = "config.urls.api_not_found"
