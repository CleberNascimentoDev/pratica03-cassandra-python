from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
import unittest
from unittest.mock import patch

from telemetria.config import Settings
from telemetria.demo_repository import DemoRepository
from telemetria.models import timestamp
from telemetria.terminal import run, simulate


class TerminalTests(unittest.TestCase):
    def test_menu_crud_and_permission_demonstration(self):
        repo = DemoRepository()
        sensor = 'sensor_cli_teste'
        when = '2026-10-24 10:00:00.123'
        query = ['3', sensor, '2026-10-24 00:00:00', '2026-10-25 00:00:00']
        commands = ['1', sensor, when, '27,5', '65', '0', *query, '4', sensor, when, '0,5', 's', *query, '6', sensor, '2026-10-24 00:00:00', '2026-10-25 00:00:00', '5', sensor, when, 's', *query, '0']
        output = StringIO()
        with patch('builtins.input', side_effect=commands), redirect_stdout(output):
            run(Settings(), repo)
        result = output.getvalue()
        for expected in ['MODO DEMO', 'Leitura inserida', 'UPDATE concluído', 'Bloqueio SIMULADO', 'role de monitoramento', 'DELETE concluído', '0 leitura(s)', 'Aplicação encerrada']:
            self.assertIn(expected, result)
        self.assertIn('0.5', result)
        point = timestamp(when)
        self.assertEqual(repo.read(sensor, point, point).rows, ())

    def test_declining_delete_preserves_reading(self):
        repo = DemoRepository()
        commands = ['1', 'sensor_cancelar', '2026-10-24 10:00:00', '25', '60', '0', '5', '', '', 'n', '0']
        with patch('builtins.input', side_effect=commands), redirect_stdout(StringIO()):
            run(Settings(), repo)
        point = timestamp('2026-10-24 10:00:00')
        self.assertEqual(len(repo.read('sensor_cancelar', point, point).rows), 1)

    def test_invalid_value_returns_to_menu(self):
        commands = ['1', 'sensor_teste', 'data inválida', '0']
        output = StringIO()
        with patch('builtins.input', side_effect=commands), redirect_stdout(output):
            run(Settings(), DemoRepository())
        self.assertIn('Data inválida', output.getvalue())
        self.assertIn('Aplicação encerrada', output.getvalue())

    def test_ctrl_c_stops_simulation_after_confirmed_write(self):
        repo, last = DemoRepository(), {}
        output = StringIO()
        with patch('builtins.input', side_effect=['sensor_parada', '10', '1']), patch('telemetria.terminal.time.sleep', side_effect=KeyboardInterrupt), redirect_stdout(output):
            simulate(repo, last)
        self.assertIn('Envio interrompido', output.getvalue())
        self.assertIn('confirmadas nesta execução: 1', output.getvalue())
        point = timestamp(last['when'])
        self.assertEqual(len(repo.read(last['sensor'], point - timedelta(seconds=1), point + timedelta(seconds=1)).rows), 1)


if __name__ == '__main__':
    unittest.main()
