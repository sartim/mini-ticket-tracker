from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    payload = response.data
    if isinstance(payload, dict) and set(payload) == {"detail"}:
        error = str(payload["detail"])
    else:
        error = payload
    response.data = {"error": error}
    return response
