from dataclasses import dataclass
from datetime import datetime, timezone
import math

from .errors import ValidationError

UTC = timezone.utc


def utc_milliseconds(value: datetime):
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    value = value.astimezone(UTC)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def timestamp(value: str):
    try:
        result = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError:
        raise ValidationError('Data inválida. Use AAAA-MM-DD HH:MM:SS, em UTC.') from None
    return utc_milliseconds(result)


def date_text(value: datetime):
    return utc_milliseconds(value).isoformat(sep=' ', timespec='milliseconds').replace('+00:00', '')


def sensor_name(value: str):
    value = value.strip()
    if not value or len(value) > 120 or any(ord(c) < 32 for c in value):
        raise ValidationError('Informe um identificador de sensor com 1 a 120 caracteres, sem caracteres de controle.')
    return value


def number(value, label):
    try:
        result = float(str(value).strip().replace(',', '.'))
    except (ValueError, TypeError):
        raise ValidationError(f'{label}: informe um número válido.') from None
    if not math.isfinite(result):
        raise ValidationError(f'{label}: o número precisa ser finito.')
    return result


@dataclass(frozen=True)
class Reading:
    sensor_id: str
    data_hora: datetime
    temperatura: float | None
    umidade: float | None
    calibracao: float | None = 0.0


@dataclass(frozen=True)
class ReadResult:
    rows: tuple[Reading, ...]
    truncated: bool = False
