"""Configuração sem credenciais fixas. Variáveis do processo prevalecem sobre .env."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import re

from .errors import ConfigurationError


def load_environment(file: Path):
    """Carrega KEY=value simples, sem executar shell, expansões ou código.

    Senhas com # são aceitas. Aspas externas são removidas. Valores existentes
    no ambiente não são sobrescritos. Reiniciar a aplicação após editar .env.
    """
    if not file.exists():
        return
    for number, line in enumerate(file.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key.strip()):
            raise ConfigurationError(f'Linha {number} inválida no arquivo .env.')
        value = value.strip()
        if value[:1] in ('"', "'"):
            if len(value) < 2 or value[-1] != value[0]:
                raise ConfigurationError(f'Aspas incompletas na linha {number} do .env.')
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


@dataclass(frozen=True)
class Settings:
    mode: str = 'demo'
    hosts: tuple[str, ...] = ()
    port: int = 0
    keyspace: str = ''
    table: str = ''
    datacenter: str = ''
    ingestor_user: str = ''
    ingestor_password: str = field(default='', repr=False)
    monitor_user: str = ''
    monitor_password: str = field(default='', repr=False)

    @classmethod
    def from_environment(cls, mode=None):
        selected = mode or os.environ.get('APP_MODE', 'demo')
        # O modo demo funciona mesmo sem configuração do Cassandra.
        if selected == 'demo':
            return cls(mode='demo')
        if selected != 'cassandra':
            raise ConfigurationError('APP_MODE deve ser demo ou cassandra.')
        try:
            port = int(os.environ.get('CASSANDRA_PORT', '0'))
        except ValueError:
            raise ConfigurationError('CASSANDRA_PORT deve ser uma porta numérica.') from None
        return cls(
            mode=selected,
            hosts=tuple(h.strip() for h in os.environ.get('CASSANDRA_HOSTS', '').split(',') if h.strip()),
            port=port,
            keyspace=os.environ.get('CASSANDRA_KEYSPACE', '').strip(),
            table=os.environ.get('CASSANDRA_TABLE', '').strip(),
            datacenter=os.environ.get('CASSANDRA_DATACENTER', '').strip(),
            ingestor_user=os.environ.get('CASSANDRA_INGESTOR_USER', '').strip(),
            ingestor_password=os.environ.get('CASSANDRA_INGESTOR_PASSWORD', ''),
            monitor_user=os.environ.get('CASSANDRA_MONITOR_USER', '').strip(),
            monitor_password=os.environ.get('CASSANDRA_MONITOR_PASSWORD', ''),
        )

    def validate_connection(self):
        if not self.hosts or not 1 <= self.port <= 65535 or not self.datacenter:
            raise ConfigurationError('Preencha host, porta e datacenter nas variáveis de ambiente.')
        for name, value in [('keyspace', self.keyspace), ('tabela', self.table)]:
            if not re.fullmatch(r'[a-z][a-z0-9_]*', value):
                raise ConfigurationError(f'Configure um nome CQL simples em minúsculas para {name}.')
        for role, user, password in [
            ('ingestor', self.ingestor_user, self.ingestor_password),
            ('monitor', self.monitor_user, self.monitor_password),
        ]:
            if not user or not password or password.startswith('<'):
                raise ConfigurationError(f'Preencha as credenciais reais do {role} no ambiente local.')
            if user.casefold() in ('cassandra', 'root', 'admin', 'administrator'):
                raise ConfigurationError('A aplicação exige roles restritas. Usuários administrativos são recusados.')
        if self.ingestor_user == self.monitor_user:
            raise ConfigurationError('Configure usuários diferentes para ingestão e monitoramento.')

    @property
    def destination(self):
        if self.mode == 'demo':
            return 'Memória local · dados simulados'
        return f'{", ".join(self.hosts) or "Host não configurado"}:{self.port or "?"}'
