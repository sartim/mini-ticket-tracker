from django.http import JsonResponse


class ApiErrorMiddleware:
    """Return a stable JSON envelope for unexpected API server errors."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if request.path.startswith("/api/v1/"):
            return JsonResponse({"error": "Internal server error."}, status=500)
        return None
