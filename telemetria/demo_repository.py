"""Simulador em memória. Não é evidência de execução nem de segurança do Cassandra."""
from dataclasses import replace
from datetime import datetime, timedelta
from threading import RLock

from .errors import PermissionDenied
from .models import UTC, Reading, ReadResult, utc_milliseconds


class DemoRepository:
    mode = 'demo'

    def __init__(self):
        self._lock = RLock()
        self._rows = {}
        now = utc_milliseconds(datetime.now(UTC))
        for sensor, offset, temp, humidity in [
            ('demo_galpao_01', 90, 27.5, 65.0),
            ('demo_galpao_01', 60, 28.5, 62.0),
            ('demo_galpao_01', 30, 30.2, 58.0),
            ('demo_galpao_02', 75, 26.8, 68.0),
            ('demo_galpao_02', 15, 27.1, 66.0),
            ('demo_deposito_01', 45, 24.3, 72.0),
        ]:
            row = Reading(sensor, now - timedelta(minutes=offset), temp, humidity)
            self._rows[(sensor, row.data_hora)] = row

    def connect(self):
        return None

    def insert(self, reading):
        with self._lock:
            self._rows[(reading.sensor_id, reading.data_hora)] = reading

    def read(self, sensor, start, end, *, role='monitor', limit=500):
        if role != 'monitor':
            raise PermissionDenied('Bloqueio simulado: o perfil de ingestão não possui SELECT.')
        with self._lock:
            rows = sorted((r for r in self._rows.values() if r.sensor_id == sensor and start <= r.data_hora <= end), key=lambda r: r.data_hora)
            return ReadResult(tuple(rows[:limit]), len(rows) > limit)

    def calibrate(self, sensor, when, value):
        with self._lock:
            old = self._rows.get((sensor, when), Reading(sensor, when, None, None, None))
            self._rows[(sensor, when)] = replace(old, calibracao=value)

    def delete(self, sensor, when):
        with self._lock:
            self._rows.pop((sensor, when), None)

    def close(self):
        return None
