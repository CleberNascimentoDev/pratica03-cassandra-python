"""Inicia pelo terminal ou pela janela simples com --gui."""
import argparse
import sys
from pathlib import Path

from telemetria.config import Settings, load_environment
from telemetria.errors import TelemetryError


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Prática 03 - Telemetria IoT com Cassandra')
    parser.add_argument('--mode', choices=('demo', 'cassandra'), help='Sobrescreve APP_MODE')
    parser.add_argument('--gui', action='store_true', help='Abre a interface gráfica simples')
    args = parser.parse_args()
    try:
        load_environment(Path(__file__).resolve().parent / '.env')
        settings = Settings.from_environment(mode=args.mode)
        if args.gui:
            from telemetria.janela import App
            App(settings).mainloop()
        else:
            from telemetria.terminal import run
            run(settings)
    except TelemetryError as error:
        print(f'Erro: {error}')
        return 1
    except KeyboardInterrupt:
        print('\nAplicação interrompida.')
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
