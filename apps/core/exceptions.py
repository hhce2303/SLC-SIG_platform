from rest_framework import status
from rest_framework.exceptions import APIException


class ServiceException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Error en la operación solicitada."
    default_code = "service_error"


class ResourceNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Recurso no encontrado."
    default_code = "not_found"


class PermissionDeniedByRole(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "No tiene permisos para realizar esta acción."
    default_code = "role_forbidden"


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflicto con el estado actual del recurso."
    default_code = "conflict"
