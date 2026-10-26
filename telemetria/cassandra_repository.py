"""Adaptador real. Somente DML com parâmetros, sem CREATE, GRANT, DROP ou TRUNCATE.

Preparação é adiada por operação: preparar SELECT com a role de ingestão pode
ser negado pelo servidor. Essa negativa precisa ocorrer no teste, não no login.
"""
from .config import Settings
from .errors import AuthenticationFailure, ConfigurationError, ConnectionFailure, PermissionDenied, TelemetryError
from .models import Reading, ReadResult, utc_milliseconds


def translate_driver_error(error):
    """Classifica erros aninhados sem incluir a mensagem bruta do driver na UI."""
    from cassandra import AuthenticationFailed, OperationTimedOut, ReadTimeout, Unauthorized, Unavailable, WriteTimeout
    from cassandra.cluster import NoHostAvailable
    if isinstance(error, AuthenticationFailed):
        return AuthenticationFailure('Autenticação recusada. Verifique as credenciais locais da role.')
    if isinstance(error, Unauthorized):
        return PermissionDenied('Cassandra negou a operação: a role não possui a permissão necessária.')
    if isinstance(error, NoHostAvailable):
        nested = [translate_driver_error(e) for e in error.errors.values()]
        for kind in (AuthenticationFailure, PermissionDenied):
            if any(isinstance(e, kind) for e in nested):
                return next(e for e in nested if isinstance(e, kind))
        return ConnectionFailure('Nenhum nó disponível. Verifique Docker, host, porta e datacenter.')
    if isinstance(error, (OperationTimedOut, ReadTimeout, WriteTimeout, Unavailable, OSError)):
        return ConnectionFailure('A conexão ou operação não foi concluída. O resultado de uma escrita pode ser incerto; consulte a chave antes de repetir.')
    return TelemetryError('Cassandra não concluiu a operação. Verifique schema, tipos e disponibilidade. Nenhuma credencial foi registrada.')


class CassandraRepository:
    mode = 'cassandra'

    def __init__(self, settings: Settings):
        self.settings = settings
        self._clusters = []
        self._sessions = {}
        self._prepared = {}

    def connect(self):
        self.settings.validate_connection()
        try:
            from cassandra.auth import PlainTextAuthProvider
            from cassandra.cluster import Cluster, ExecutionProfile, EXEC_PROFILE_DEFAULT
            from cassandra.policies import DCAwareRoundRobinPolicy, TokenAwarePolicy
        except ImportError:
            raise ConfigurationError('Instale requirements-cassandra.txt no ambiente virtual para usar Cassandra real.') from None
        self.close()
        try:
            for name, user, password in [
                ('ingestor', self.settings.ingestor_user, self.settings.ingestor_password),
                ('monitor', self.settings.monitor_user, self.settings.monitor_password),
            ]:
                profile = ExecutionProfile(load_balancing_policy=TokenAwarePolicy(DCAwareRoundRobinPolicy(local_dc=self.settings.datacenter)), request_timeout=8.0)
                cluster = Cluster(
                    contact_points=list(self.settings.hosts), port=self.settings.port,
                    auth_provider=PlainTextAuthProvider(username=user, password=password),
                    execution_profiles={EXEC_PROFILE_DEFAULT: profile},
                    connect_timeout=8.0, control_connection_timeout=8.0,
                )
                self._clusters.append(cluster)
                self._sessions[name] = cluster.connect(self.settings.keyspace)
        except Exception as error:
            self.close()
            raise translate_driver_error(error) from None

    def _execute(self, operation, role, query, values):
        if role not in self._sessions:
            raise ConnectionFailure('Conecte os dois perfis antes de executar esta operação.')
        session = self._sessions[role]
        try:
            cache_key = (operation, role)
            if cache_key not in self._prepared:
                self._prepared[cache_key] = session.prepare(query)
            return session.execute(self._prepared[cache_key], values)
        except Exception as error:
            raise translate_driver_error(error) from None

    @property
    def _table(self):
        # Identificadores validados em Settings; valores sempre são vinculados com ?.
        return f'{self.settings.keyspace}.{self.settings.table}'

    def insert(self, reading):
        self._execute('insert', 'ingestor',
            f'INSERT INTO {self._table} (sensor_id, data_hora, temperatura, umidade, calibracao) VALUES (?, ?, ?, ?, ?)',
            (reading.sensor_id, reading.data_hora, reading.temperatura, reading.umidade, reading.calibracao))

    def read(self, sensor, start, end, *, role='monitor', limit=500):
        result = self._execute('read', role,
            f'SELECT sensor_id, data_hora, temperatura, umidade, calibracao FROM {self._table} WHERE sensor_id = ? AND data_hora >= ? AND data_hora <= ? ORDER BY data_hora ASC LIMIT ?',
            (sensor, start, end, limit + 1))
        try:
            rows = tuple(Reading(r.sensor_id, utc_milliseconds(r.data_hora), r.temperatura, r.umidade, r.calibracao) for r in result)
            return ReadResult(rows[:limit], len(rows) > limit)
        except Exception as error:
            raise translate_driver_error(error) from None

    def calibrate(self, sensor, when, value):
        self._execute('calibrate', 'ingestor',
            f'UPDATE {self._table} SET calibracao = ? WHERE sensor_id = ? AND data_hora = ?', (value, sensor, when))

    def delete(self, sensor, when):
        self._execute('delete', 'ingestor',
            f'DELETE FROM {self._table} WHERE sensor_id = ? AND data_hora = ?', (sensor, when))

    def close(self):
        for cluster in self._clusters:
            try:
                cluster.shutdown()
            except Exception:
                pass
        self._clusters.clear()
        self._sessions.clear()
        self._prepared.clear()
