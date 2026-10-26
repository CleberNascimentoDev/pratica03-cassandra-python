# Executar no computador com Cassandra

Usar este roteiro depois de publicar o projeto no GitHub. Preservar o banco da Prática 02.

## 1. Clonar e instalar

No PowerShell, com Git e Python 3.10 a 3.14 instalados:

```powershell
git clone https://github.com/CleberNascimentoDev/pratica03-cassandra-python.git
cd pratica03-cassandra-python
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-cassandra.txt
.\.venv\Scripts\python.exe main.py --mode demo
```

Autenticar no GitHub com uma conta que tenha acesso ao repositório privado. Testar o menu local primeiro. Não copiar a `.venv` original.

## 2. Verificar o Cassandra existente

```powershell
docker ps -a
docker exec cassandra nodetool status
docker port cassandra 9042
Test-NetConnection -ComputerName 127.0.0.1 -Port 9042
```

Se estiver parado, iniciar o contêiner existente com `docker start cassandra` e aguardar. UN significa nó ativo e normal. Anotar o nome do datacenter exibido no nodetool.

Aplicação e Docker devem rodar no mesmo computador neste roteiro. O ambiente anterior usava 127.0.0.1:9042. Um reinício não publica uma porta que não foi publicada na criação do contêiner; se esse for o problema, revisar criação e volume antes de qualquer recriação. Não remover cassandra_dados nem expor o banco à rede.

## 3. Conferir schema e roles

Administrador somente no cqlsh, fora da aplicação:

```powershell
docker exec -it cassandra cqlsh -u cassandra --disable-history
```

Digitar a senha no prompt. No CQL:

```sql
DESCRIBE KEYSPACE telemetria_iot;
DESCRIBE TABLE telemetria_iot.leituras_sensores;
LIST ROLES;
LIST ALL PERMISSIONS OF ingestor_iot;
```

Conferir PRIMARY KEY ((sensor_id), data_hora) e os campos double temperatura, umidade e calibracao. O ingestor precisa de LOGIN, sem SUPERUSER, com MODIFY na tabela e sem SELECT direto nem herdado.

Preservar PasswordAuthenticator e CassandraAuthorizer da Prática 02. Se não estiverem ativos, revisar a segurança antes de integrar.

Se ainda não houver uma role restrita de monitoramento, o administrador pode criar:

```sql
CREATE ROLE monitor_iot
WITH PASSWORD = '<SENHA_FORTE_DO_MONITOR>'
AND LOGIN = true
AND SUPERUSER = false;

GRANT SELECT ON TABLE telemetria_iot.leituras_sensores TO monitor_iot;
LIST ALL PERMISSIONS OF monitor_iot;
```

Substituir a senha apenas na sessão privada, nunca nos arquivos versionados. Se a role já existir, conferir seus privilégios em vez de repetir CREATE. O monitor deve ter somente leitura na tabela, sem privilégios administrativos. MODIFY também permite UPDATE, DELETE e TRUNCATE; não afirmar que o ingestor tem apenas INSERT.

## 4. Configurar o .env

Na pasta clonada, copiar somente se `.env` ainda não existir:

```powershell
Copy-Item .env.example .env
notepad .env
```

Preencher APP_MODE=cassandra, host, porta, datacenter, keyspace, tabela e credenciais das duas roles. Usar o datacenter informado pelo nodetool. O `.env.example` contém os nomes de todas as variáveis, com senhas vazias. Variáveis do processo prevalecem sobre o arquivo. Reiniciar a aplicação após editar a configuração.

Não usar administrador na aplicação nem gravar senhas em comandos setx, GitHub ou capturas.

## 5. Executar e demonstrar

```powershell
.\.venv\Scripts\python.exe main.py --mode cassandra
```

As duas roles conectam ao iniciar. Se a conexão falhar, conferir o ambiente e usar a opção 7, ou reiniciar se o `.env` mudou.

1. Opção 3: consultar sensor_galpao_01, de 2026-10-18 00:00:00 a 2026-10-21 23:59:59.999, em UTC.
2. Opção 6: repetir sensor e intervalo. Deve negar SELECT ao ingestor e consultar com o monitor. Uma leitura permitida ao ingestor será sinalizada para revisão.
3. Opção 2: aceitar o novo sensor sugerido, enviar poucas leituras e copiar uma chave exata exibida.
4. Opção 3: consultar o novo sensor. Enter aceita o último sensor e o intervalo recente sugeridos.
5. Opção 4: atualizar a calibração de uma nova leitura e confirmar com s. Consultar novamente para verificar.
6. Opção 5: excluir somente uma nova leitura e confirmar com s. Consultar para verificar a ausência.
7. Opção 0: sair.

Preservar os dados históricos da Prática 02. Cada envio real acrescenta medições. Dados fictícios do modo demo nunca são transferidos ao Cassandra.

## Problemas comuns

- Driver ausente ou default connection class indisponível: instalar requirements-cassandra.txt, incluindo pyasyncore no Python 3.12+.
- Nenhum nó disponível: verificar Docker, contêiner, host, porta publicada e datacenter.
- Autenticação recusada: conferir senha local e LOGIN da role.
- SELECT negado ao monitor: conferir SELECT na tabela e caches de autorização.
- SELECT permitido ao ingestor: revisar permissões diretas/herdadas e authorizer do servidor.
- Consulta vazia: conferir modo, identificador e intervalo UTC.
- Linha parcial após UPDATE: a chave não existia; esse é o comportamento de upsert sem IF EXISTS.
- Timeout durante escrita: o resultado pode ser incerto; consultar a mesma chave antes de repetir.

A validação com Cassandra real permanece pendente até a execução no computador de destino.

Para usar a janela simples no mesmo ambiente:

```powershell
.\.venv\Scripts\python.exe main.py --gui --mode cassandra
```

Clicar em Conectar, preencher os campos e usar os botões equivalentes às opções do terminal. Selecionar uma linha da tabela copia a chave para os campos. O Python deve incluir Tcl/Tk. A janela e o terminal usam os mesmos repositórios e permissões.

