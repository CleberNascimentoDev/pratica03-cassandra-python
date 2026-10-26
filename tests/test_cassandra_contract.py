"""Contrato do adaptador com sessões falsas. Não abre sockets nem usa banco."""
from importlib.util import find_spec
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from telemetria.cassandra_repository import CassandraRepository, translate_driver_error
from telemetria.config import Settings
from telemetria.errors import AuthenticationFailure, PermissionDenied
from telemetria.models import timestamp
from telemetria.services import new_reading


@unittest.skipUnless(find_spec('cassandra'), 'Driver opcional não instalado')
class PreparedStatementTests(unittest.TestCase):
    def setUp(self):
        self.repo = CassandraRepository(Settings(keyspace='telemetria_iot', table='leituras_sensores'))
        self.ingestor = MagicMock()
        self.monitor = MagicMock()
        self.repo._sessions = {'ingestor': self.ingestor, 'monitor': self.monitor}
        self.when = timestamp('2026-10-21 10:00:00.123Z')

    def test_sensor_value_is_bound_and_statement_is_reused(self):
        sensor = "sensor_'_valor_que_nao_pode_ser_sql"
        row = new_reading(sensor, 25, 60, when=self.when)
        self.repo.insert(row)
        self.repo.insert(row)
        self.ingestor.prepare.assert_called_once()
        cql = self.ingestor.prepare.call_args.args[0]
        self.assertNotIn(sensor, cql)
        self.assertEqual(cql.count('?'), 5)
        self.assertEqual(self.ingestor.execute.call_args.args[1][0], sensor)
        self.monitor.execute.assert_not_called()

    def test_update_and_delete_bind_full_primary_key(self):
        self.repo.calibrate('sensor', self.when, .5)
        self.assertEqual(self.ingestor.execute.call_args.args[1], (.5, 'sensor', self.when))
        self.repo.delete('sensor', self.when)
        self.assertEqual(self.ingestor.execute.call_args.args[1], ('sensor', self.when))

    def test_monitor_reads_and_driver_naive_utc_is_normalized(self):
        self.monitor.execute.return_value = [SimpleNamespace(sensor_id='sensor', data_hora=self.when.replace(tzinfo=None), temperatura=25, umidade=60, calibracao=.5)]
        result = self.repo.read('sensor', self.when, self.when)
        self.assertEqual(result.rows[0].data_hora, self.when)
        cql = self.monitor.prepare.call_args.args[0]
        self.assertIn('ORDER BY data_hora ASC', cql)
        self.assertNotIn('ALLOW FILTERING', cql)
        self.ingestor.execute.assert_not_called()

    def test_authorization_failure_can_happen_during_prepare(self):
        from cassandra import Unauthorized
        self.ingestor.prepare.side_effect = Unauthorized('mensagem_original_privada')
        with self.assertRaises(PermissionDenied) as caught:
            self.repo.read('sensor', self.when, self.when, role='ingestor')
        self.assertNotIn('mensagem_original_privada', str(caught.exception))

    def test_nested_authentication_error_is_classified_without_raw_message(self):
        from cassandra import AuthenticationFailed
        from cassandra.cluster import NoHostAvailable
        error = NoHostAvailable('erro_original', {'host': AuthenticationFailed('credencial_nao_exibir')})
        translated = translate_driver_error(error)
        self.assertIsInstance(translated, AuthenticationFailure)
        self.assertNotIn('credencial_nao_exibir', str(translated))


if __name__ == '__main__':
    unittest.main()
