from datetime import datetime, timedelta
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from telemetria.config import Settings, load_environment
from telemetria.demo_repository import DemoRepository
from telemetria.errors import ConfigurationError, PermissionDenied, ValidationError
from telemetria.models import UTC, date_text, number, timestamp
from telemetria.services import new_reading, simulation_parameters, validate_interval


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.repo = DemoRepository()
        self.when = timestamp('2026-10-21 10:00:00.123+00:00')
        self.row = new_reading('sensor_exclusivo_teste', '27,5', '65', when=self.when)

    def read(self):
        return self.repo.read(self.row.sensor_id, self.when - timedelta(seconds=1), self.when + timedelta(seconds=1)).rows

    def test_crud_preserves_other_metrics_and_exact_key(self):
        self.repo.insert(self.row)
        other = new_reading(self.row.sensor_id, 30, 60, when=self.when + timedelta(milliseconds=1))
        self.repo.insert(other)
        self.repo.calibrate(self.row.sensor_id, self.when, .5)
        rows = self.read()
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0].temperatura, rows[0].umidade, rows[0].calibracao), (27.5, 65, .5))
        self.repo.delete(self.row.sensor_id, self.when)
        self.assertEqual(self.read(), (other,))
        self.repo.delete(self.row.sensor_id, self.when)  # DELETE idempotente
        self.assertEqual(self.read(), (other,))

    def test_upsert_on_absent_key_creates_partial_row(self):
        self.repo.calibrate(self.row.sensor_id, self.when, .75)
        row = self.read()[0]
        self.assertIsNone(row.temperatura)
        self.assertIsNone(row.umidade)
        self.assertEqual(row.calibracao, .75)

    def test_ingestor_read_is_explicitly_simulated_denial(self):
        with self.assertRaisesRegex(PermissionDenied, 'simulado'):
            self.repo.read('sensor_qualquer', self.when, self.when, role='ingestor')

    def test_interval_is_inclusive_ordered_and_reports_truncation(self):
        for i in (2, 0, 1):
            self.repo.insert(new_reading(self.row.sensor_id, 20 + i, 60, when=self.when + timedelta(seconds=i)))
        result = self.repo.read(self.row.sensor_id, self.when, self.when + timedelta(seconds=2), limit=2)
        self.assertEqual([r.temperatura for r in result.rows], [20, 21])
        self.assertTrue(result.truncated)
        single = self.repo.read(self.row.sensor_id, self.when, self.when)
        self.assertEqual(len(single.rows), 1)

    def test_dates_keep_millisecond_key_across_timezones(self):
        self.assertEqual(timestamp('2026-10-21 07:00:00.123999-03:00'), self.when)
        self.assertEqual(timestamp(date_text(self.when)), self.when)

    def test_invalid_measurements_and_intervals_are_rejected(self):
        for value in ('nan', 'inf', '-inf', 'abc'):
            with self.assertRaises(ValidationError):
                number(value, 'Valor')
        with self.assertRaises(ValidationError):
            new_reading('sensor', 20, 101)
        with self.assertRaises(ValidationError):
            new_reading('', 20, 50)
        with self.assertRaises(ValidationError):
            validate_interval(self.when + timedelta(seconds=1), self.when)
        for count, interval in [('0', '1'), ('2.5', '1'), ('5', '0'), ('5', 'nan')]:
            with self.assertRaises(ValidationError):
                simulation_parameters(count, interval)


class ConfigurationTests(unittest.TestCase):
    def test_demo_needs_no_credentials_even_with_invalid_real_port(self):
        with patch.dict(os.environ, {'CASSANDRA_PORT': 'incorreta'}, clear=True):
            self.assertEqual(Settings.from_environment().mode, 'demo')

    def test_environment_overrides_env_file_and_hash_is_literal(self):
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / '.env'
            env.write_text('APP_MODE=cassandra\nCASSANDRA_INGESTOR_PASSWORD="ficticio#apenas_teste"\n', encoding='utf-8')
            with patch.dict(os.environ, {'APP_MODE': 'demo'}, clear=True):
                load_environment(env)
                self.assertEqual(os.environ['APP_MODE'], 'demo')
                self.assertEqual(os.environ['CASSANDRA_INGESTOR_PASSWORD'], 'ficticio#apenas_teste')

    def test_credentials_are_not_exposed_in_repr(self):
        config = Settings(ingestor_password='marcador_ingestor', monitor_password='marcador_monitor')
        self.assertNotIn('marcador_ingestor', repr(config))
        self.assertNotIn('marcador_monitor', repr(config))

    def valid_settings(self, **kwargs):
        data = dict(mode='cassandra', hosts=('127.0.0.1',), port=9042, datacenter='datacenter1', keyspace='telemetria_iot', table='leituras_sensores', ingestor_user='ingestor_iot', ingestor_password='ficticio_teste', monitor_user='monitor_iot', monitor_password='ficticio_teste')
        data.update(kwargs)
        return Settings(**data)

    def test_admin_and_unsafe_identifiers_are_rejected(self):
        for user in ('cassandra', 'ROOT', 'admin'):
            with self.assertRaises(ConfigurationError):
                self.valid_settings(ingestor_user=user).validate_connection()
        with self.assertRaises(ConfigurationError):
            self.valid_settings(table='leituras; DROP TABLE outra').validate_connection()
        with self.assertRaises(ConfigurationError):
            self.valid_settings(monitor_user='ingestor_iot').validate_connection()


if __name__ == '__main__':
    unittest.main()
