import time
import unittest
from unittest.mock import patch

from telemetria.config import Settings
from telemetria.janela import App


class JanelaTests(unittest.TestCase):
    def setUp(self):
        self.app = App(Settings())
        self.app.withdraw()
        self.errors = []
        self.app.error = self.errors.append

    def tearDown(self):
        self.app.destroy()

    def wait_idle(self):
        start = time.monotonic()
        while time.monotonic() - start < 5:
            self.app.update()
            if not self.app.busy:
                return
            time.sleep(.01)
        self.fail('Operação não terminou.')

    def test_crud_and_permission_flow(self):
        self.app.new_sensor()
        self.app.insert()
        self.wait_idle()
        self.app.read()
        self.wait_idle()
        self.assertEqual(len(self.app.rows), 1)
        self.app.table.selection_set('0')
        self.app.select_row()
        self.app.calibration.set('0,5')
        with patch('telemetria.janela.messagebox.askyesno', return_value=True):
            self.app.calibrate()
        self.wait_idle()
        self.app.read()
        self.wait_idle()
        self.assertEqual(self.app.rows[0].calibracao, .5)
        self.app.permissions()
        self.wait_idle()
        self.assertIn('Bloqueio SIMULADO', self.app.output.get('1.0', 'end'))
        with patch('telemetria.janela.messagebox.askyesno', return_value=True):
            self.app.delete()
        self.wait_idle()
        self.app.read()
        self.wait_idle()
        self.assertEqual(self.app.rows, ())
        self.assertEqual(self.errors, [])

    def test_simulation_stops_without_blocking_window(self):
        self.app.new_sensor()
        self.app.count.set('100')
        self.app.delay.set('0,1')
        self.app.simulate()
        start = time.monotonic()
        while 'Enviada 2/' not in self.app.output.get('1.0', 'end') and time.monotonic() - start < 3:
            self.app.update()
            time.sleep(.01)
        self.app.stop.set()
        self.wait_idle()
        self.app.read()
        self.wait_idle()
        self.assertGreaterEqual(len(self.app.rows), 2)
        self.assertLess(len(self.app.rows), 100)
        self.assertEqual(self.errors, [])

    def test_invalid_date_does_not_start_operation(self):
        self.app.start.set('data inválida')
        self.app.read()
        self.assertFalse(self.app.busy)
        self.assertIn('Data inválida', self.errors[0])


if __name__ == '__main__':
    unittest.main()
