"""Menu simples para demonstrar as operações da atividade."""
from datetime import datetime, timedelta
import time
import uuid

from .demo_repository import DemoRepository
from .errors import AuthenticationFailure, ConnectionFailure, PermissionDenied, TelemetryError
from .models import UTC, date_text, number, sensor_name, timestamp
from .services import new_reading, simulated_reading, simulation_parameters, validate_interval


def ask(label, default=''):
    prompt = f'{label} [{default}]: ' if default != '' else f'{label}: '
    value = input(prompt).strip()
    return value or default


def key(last):
    sensor = sensor_name(ask('Sensor', last.get('sensor', '')))
    when = timestamp(ask('Data e hora exatas (UTC)', last.get('when', '')))
    return sensor, when


def interval(last, mode):
    example = 'demo_galpao_01' if mode == 'demo' else 'sensor_galpao_01'
    sensor = sensor_name(ask('Sensor', last.get('sensor', example)))
    now = datetime.now(UTC)
    start = timestamp(ask('Início (UTC)', date_text(now - timedelta(days=1))))
    end = timestamp(ask('Fim (UTC)', date_text(now + timedelta(seconds=5))))
    validate_interval(start, end)
    return sensor, start, end


def show_rows(result):
    print(f'\n{"Data e hora (UTC)":<27} {"Temp. °C":>10} {"Umid. %":>10} {"Calibração":>12}')
    print('-' * 65)
    for row in result.rows:
        values = ['-' if value is None else f'{value:.1f}' for value in (row.temperatura, row.umidade, row.calibracao)]
        print(f'{date_text(row.data_hora):<27} {values[0]:>10} {values[1]:>10} {values[2]:>12}')
    print(f'{len(result.rows)} leitura(s).')
    if result.truncated:
        print('Limite de 500 leituras atingido. Reduza o intervalo para consultar as demais.')


def insert(repo, last):
    sensor = sensor_name(ask('Sensor', 'sensor_demo_' + uuid.uuid4().hex))
    when = timestamp(ask('Data e hora (UTC)', date_text(datetime.now(UTC))))
    temp = ask('Temperatura (°C)')
    humidity = ask('Umidade (%)')
    calibration = ask('Calibração', '0')
    row = new_reading(sensor, temp, humidity, calibration, when)
    repo.insert(row)
    last.update(sensor=sensor, when=date_text(when))
    print(f'Leitura inserida: {sensor} / {date_text(when)} UTC.')


def simulate(repo, last):
    sensor = sensor_name(ask('Sensor', 'sensor_demo_' + uuid.uuid4().hex))
    count, delay = simulation_parameters(ask('Quantidade de leituras', '10'), ask('Intervalo em segundos', '1'))
    print('Enviando leituras. Ctrl+C interrompe o envio e retorna ao menu.')
    sent = 0
    try:
        for i in range(count):
            row = simulated_reading(sensor)
            repo.insert(row)
            last.update(sensor=sensor, when=date_text(row.data_hora))
            sent += 1
            print(f'{sent}/{count} - {date_text(row.data_hora)} UTC - {row.temperatura} °C - {row.umidade}%')
            if i < count - 1:
                time.sleep(delay)
    except KeyboardInterrupt:
        print('\nEnvio interrompido.')
    finally:
        print(f'Leituras confirmadas nesta execução: {sent}.')


def read(repo, last, mode):
    sensor, start, end = interval(last, mode)
    print(f'\nConsulta do sensor {sensor} com a role de monitoramento:')
    show_rows(repo.read(sensor, start, end))


def calibrate(repo, last):
    sensor, when = key(last)
    value = number(ask('Nova calibração'), 'Calibração')
    print('UPDATE é upsert: uma chave inexistente pode criar uma linha parcial.')
    if ask('Confirmar atualização? (s/N)', 'n').lower() != 's':
        print('Atualização cancelada.')
        return
    repo.calibrate(sensor, when, value)
    print('UPDATE concluído. Consulte o histórico para conferir a calibração.')


def delete(repo, last):
    sensor, when = key(last)
    print(f'Excluir somente {sensor} / {date_text(when)} UTC.')
    if ask('Confirmar exclusão? (s/N)', 'n').lower() != 's':
        print('Exclusão cancelada.')
        return
    repo.delete(sensor, when)
    print('DELETE concluído. Consulte o histórico para confirmar a ausência.')
    print('O comando não informa se a leitura já estava ausente.')


def permissions(repo, last, mode):
    sensor, start, end = interval(last, mode)
    try:
        repo.read(sensor, start, end, role='ingestor', limit=1)
    except PermissionDenied:
        print('Bloqueio SIMULADO: o ingestor não possui SELECT.' if mode == 'demo' else 'Cassandra negou SELECT ao ingestor, conforme esperado.')
    else:
        print('Atenção: SELECT foi permitido ao ingestor. Revise as permissões no banco.')
    print('\nAgora consultando a mesma partição com a role de monitoramento:')
    show_rows(repo.read(sensor, start, end))


def run(settings, repository=None):
    if repository is None:
        if settings.mode == 'demo':
            repository = DemoRepository()
        else:
            from .cassandra_repository import CassandraRepository
            repository = CassandraRepository(settings)
    repo = repository
    last = {}
    connected = False
    print('Prática 03 - Cassandra / Telemetria IoT')
    print('Dupla 3 - Cleber e Leonardo')
    print('MODO DEMO: dados fictícios em memória, sem Cassandra.' if settings.mode == 'demo' else 'MODO CASSANDRA: operações no banco configurado no ambiente.')
    print('Datas no formato AAAA-MM-DD HH:MM:SS. Milissegundos são aceitos. Horários em UTC.')
    actions = {
        '1': lambda: insert(repo, last),
        '2': lambda: simulate(repo, last),
        '3': lambda: read(repo, last, settings.mode),
        '4': lambda: calibrate(repo, last),
        '5': lambda: delete(repo, last),
        '6': lambda: permissions(repo, last, settings.mode),
    }
    try:
        try:
            repo.connect()
            connected = True
            print('Simulador local pronto.' if settings.mode == 'demo' else 'Conexões de ingestão e monitoramento estabelecidas.')
        except TelemetryError as error:
            print(f'Erro de conexão: {error}')
        while True:
            print('\n1 - Inserir leitura\n2 - Simular envio de sensor\n3 - Consultar por intervalo\n4 - Atualizar calibração\n5 - Excluir leitura inválida\n6 - Testar permissões\n7 - Reconectar\n0 - Sair')
            try:
                choice = input('Opção: ').strip()
            except (EOFError, KeyboardInterrupt):
                break
            if choice == '0':
                break
            try:
                if choice == '7':
                    connected = False
                    repo.connect()
                    connected = True
                    print('Conexão restabelecida.')
                elif choice not in actions:
                    print('Opção inválida.')
                elif not connected:
                    print('Sem conexão. Use a opção 7 para tentar novamente.')
                else:
                    actions[choice]()
            except (AuthenticationFailure, ConnectionFailure) as error:
                connected = False
                print(f'Erro: {error}')
            except TelemetryError as error:
                print(f'Erro: {error}')
            except EOFError:
                break
            except KeyboardInterrupt:
                print('\nOperação interrompida. Retornando ao menu.')
            except Exception:
                print('Não foi possível concluir a operação. Verifique a configuração e tente novamente.')
    finally:
        repo.close()
        print('\nAplicação encerrada.')
