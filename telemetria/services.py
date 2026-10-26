"""Validações de negócio e geração de medições independentes da interface."""
from datetime import datetime
import random

from .errors import ValidationError
from .models import UTC, Reading, number, sensor_name, utc_milliseconds


def new_reading(sensor, temp, humidity, calibration=0.0, when=None):
    humidity = number(humidity, 'Umidade')
    if not 0 <= humidity <= 100:
        raise ValidationError('A umidade deve estar entre 0 e 100%.')
    return Reading(sensor_name(sensor), utc_milliseconds(when or datetime.now(UTC)), number(temp, 'Temperatura'), humidity, number(calibration, 'Calibração'))


def simulated_reading(sensor):
    return new_reading(sensor, round(random.uniform(23.0, 32.0), 1), round(random.uniform(50.0, 75.0), 1))


def validate_interval(start, end):
    if start > end:
        raise ValidationError('O início do intervalo precisa ser anterior ou igual ao fim.')


def simulation_parameters(count, interval):
    try:
        count = int(count)
    except ValueError:
        raise ValidationError('A quantidade precisa ser um número inteiro.') from None
    interval = number(interval, 'Intervalo')
    if not 1 <= count <= 10000:
        raise ValidationError('Informe de 1 a 10.000 leituras por execução.')
    if not 0.1 <= interval <= 3600:
        raise ValidationError('O intervalo precisa estar entre 0,1 e 3.600 segundos.')
    return count, interval
