"""Erros que podem ser mostrados na interface sem revelar credenciais."""


class TelemetryError(Exception):
    """Erro esperado na aplicação."""


class ValidationError(TelemetryError):
    pass


class ConfigurationError(TelemetryError):
    pass


class ConnectionFailure(TelemetryError):
    pass


class AuthenticationFailure(TelemetryError):
    pass


class PermissionDenied(TelemetryError):
    pass
