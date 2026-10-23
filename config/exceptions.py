from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Format d'erreur homogene : {"detail": str, "errors": {champ: [messages]}}."""
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if isinstance(data, dict) and "detail" in data and len(data) == 1:
        response.data = {"detail": str(data["detail"]), "errors": {}}
    elif isinstance(data, dict):
        response.data = {"detail": "Certaines informations sont invalides.", "errors": data}
    elif isinstance(data, list):
        response.data = {"detail": " ".join(str(x) for x in data), "errors": {}}
    return response
