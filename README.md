# Prática 03 - Cassandra com Python

Dupla 3: Cleber e Leonardo.

Aplicação para demonstrar CRUD e permissões sobre as leituras de sensores da Prática 02. Pode ser usada pelo terminal ou por uma janela simples.

## Executar

No PowerShell, dentro desta pasta:

```powershell
.\.venv\Scripts\python.exe main.py --mode demo
```

Também pode usar `iniciar.ps1`. Se o PowerShell bloquear o arquivo, usar diretamente o comando Python, sem mudar a política do Windows.

A `.venv` já está criada neste computador. Para preparar outro ambiente, usar Python 3.10 a 3.14 e executar `py -3 -m venv .venv`. O modo demo não precisa de pacotes externos.

## Janela simples

Para abrir o formulário gráfico:

```powershell
.\.venv\Scripts\python.exe main.py --gui --mode demo
```

Também pode executar `iniciar_gui.ps1`. A janela usa o Tkinter incluído na instalação oficial do Python para Windows, sem pacotes gráficos extras. Se o módulo não estiver disponível, habilitar Tcl/Tk no instalador do Python.

O formulário contém campos para a leitura, filtros de intervalo, botões das operações, simulação e uma tabela de resultados. Selecionar uma linha preenche os campos com a chave exata para atualizar ou excluir. O botão **Novo sensor** gera um ID exclusivo. A simulação gera temperatura e umidade automaticamente e usa calibração inicial zero.

No modo real, usar `--gui --mode cassandra` e clicar em **Conectar**. As credenciais continuam no ambiente ou `.env`, sem campos de senha na janela. O botão de teste tenta SELECT como ingestor e consulta a mesma partição como monitor. O modo demo identifica o bloqueio como simulado.

## Menu no terminal

```text
1 - Inserir leitura
2 - Simular envio de sensor
3 - Consultar por intervalo
4 - Atualizar calibração
5 - Excluir leitura inválida
6 - Testar permissões
7 - Reconectar
0 - Sair
```

Enter aceita o valor sugerido entre colchetes. Números aceitam ponto ou vírgula. As datas são UTC, no formato `2026-10-24 10:00:00.123`. Preservar os milissegundos ao copiar a chave de uma medição.

A simulação envia a quantidade informada com pausa entre leituras. Ctrl+C interrompe o envio e volta ao menu. A consulta filtra um sensor por intervalo inclusivo e ordena por data. Retorna até 500 linhas e avisa quando esse limite é atingido.

UPDATE e DELETE usam a chave completa (sensor_id e data_hora) e pedem confirmação. UPDATE é upsert: uma chave ausente pode criar uma linha parcial. DELETE não retorna uma contagem de linhas afetadas; verificar a ausência pelo histórico.

## Modos

- `demo`: seis leituras fictícias e operações em memória, sem conexão ao banco. Os dados somem ao encerrar. O bloqueio de SELECT é simulado e identificado como tal.
- `cassandra`: operações no banco configurado no ambiente. Escritas usam a role de ingestão, consultas usam a de monitoramento. A opção 6 testa o SELECT com o ingestor e depois consulta com o monitor.

Para o modo real:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-cassandra.txt
.\.venv\Scripts\python.exe main.py --mode cassandra
```

Antes, preencher um `.env` local a partir de `.env.example`, sem sobrescrever um `.env` já existente. Ver [o roteiro do outro computador](docs/OUTRO_COMPUTADOR.md). A validação com Cassandra real ainda precisa acontecer naquele computador.

## Código

```text
main.py                         Entrada do programa
telemetria/terminal.py          Menu e entrada de dados
telemetria/janela.py            Formulário gráfico simples
telemetria/config.py            Variáveis de ambiente e .env
telemetria/models.py            Leituras e timestamps
telemetria/services.py          Validações e geração de medições
telemetria/repository.py        Contrato de persistência
telemetria/demo_repository.py   Simulador em memória
telemetria/cassandra_repository.py  Conexões e comandos CQL
telemetria/errors.py            Erros tratados
```

A conexão e os comandos ficam separados do menu. O adaptador real usa Prepared Statements com valores vinculados. Falhas de conexão, autenticação e autorização são tratadas sem imprimir senhas. Uma queda ou timeout durante escrita pode deixar o resultado incerto; consultar a mesma chave antes de repetir.

Usuário, senha, host e porta vêm do ambiente ou do arquivo `.env`. Variáveis do processo prevalecem sobre o arquivo. Não usar administrador na aplicação. Confirmar LOGIN, SUPERUSER e permissões pelo cqlsh administrativo: o nome da role não comprova seus privilégios.

MODIFY permite INSERT, UPDATE, DELETE e TRUNCATE no Cassandra. O programa oferece apenas as operações do exercício e não executa CREATE, GRANT, DROP ou TRUNCATE. TLS e auditoria não são configurados pela aplicação.

## GitHub e testes

Repositório: [CleberNascimentoDev/pratica03-cassandra-python](https://github.com/CleberNascimentoDev/pratica03-cassandra-python).

Versionar esta pasta sem `.venv`, `.env`, logs ou caches, já excluídos pelo `.gitignore`. Incluir `.env.example` com senhas vazias. Recriar a `.venv` após clonar no outro computador.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes usam dados fictícios e sessões falsas, sem servidor Cassandra. Testes do adaptador são ignorados se o driver opcional não estiver instalado.
Os testes da janela precisam de Tkinter e de uma sessão gráfica disponível.

## Referências

- [Driver Python Apache Cassandra](https://github.com/apache/cassandra-python-driver)
- [Instalação e event loops](https://github.com/apache/cassandra-python-driver/blob/trunk/docs/installation.rst)
- [Roles e permissões](https://cassandra.apache.org/doc/stable/cassandra/developing/cql/security.html)

As dependências reais incluem pyasyncore no Python 3.12+ para compatibilidade com o reactor padrão do driver no Windows.

