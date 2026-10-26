"""Formulário Tkinter simples. Reutiliza os mesmos repositórios do terminal."""
from datetime import datetime, timedelta
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import uuid

from .demo_repository import DemoRepository
from .errors import AuthenticationFailure, ConnectionFailure, PermissionDenied, TelemetryError
from .models import UTC, date_text, number, sensor_name, timestamp
from .services import new_reading, simulated_reading, simulation_parameters, validate_interval


class App(tk.Tk):
    def __init__(self, settings, repository=None):
        super().__init__()
        self.title('Prática 03 - Cassandra - Dupla 3')
        self.geometry('930x700')
        self.minsize(900, 680)
        self.settings = settings
        if repository is None:
            if settings.mode == 'demo':
                repository = DemoRepository()
            else:
                from .cassandra_repository import CassandraRepository
                repository = CassandraRepository(settings)
        self.repo = repository
        self.connected = settings.mode == 'demo'
        self.busy = self.closing = self.destroyed = False
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.buttons, self.rows = [], ()
        now = datetime.now(UTC)
        self.sensor = tk.StringVar(value='demo_galpao_01' if self.connected else self.unique_sensor())
        self.when = tk.StringVar(value=date_text(now))
        self.temp = tk.StringVar(value='27,5')
        self.humidity = tk.StringVar(value='65')
        self.calibration = tk.StringVar(value='0')
        self.start = tk.StringVar(value=date_text(now - timedelta(days=1)))
        self.end = tk.StringVar(value=date_text(now + timedelta(hours=1)))
        self.count = tk.StringVar(value='10')
        self.delay = tk.StringVar(value='1')
        self.status = tk.StringVar()
        self.build()
        self.refresh_status()
        self.log('Demonstração: dados fictícios em memória, sem Cassandra.' if self.connected else 'Clique em Conectar. A configuração será lida do ambiente local.')
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(80, self.poll)

    @staticmethod
    def unique_sensor():
        return 'sensor_demo_' + uuid.uuid4().hex

    def button(self, parent, label, command):
        button = ttk.Button(parent, text=label, command=command)
        button.pack(side='left', padx=(0, 8), pady=4)
        self.buttons.append(button)
        return button

    def field(self, parent, label, variable, row, column, width=26, span=1):
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky='w', padx=(0, 6), pady=5)
        entry = ttk.Entry(parent, textvariable=variable, width=width)
        entry.grid(row=row, column=column + 1, columnspan=span, sticky='ew', padx=(0, 12), pady=5)

    def build(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill='both', expand=True)
        header = ttk.Frame(main)
        header.pack(fill='x')
        ttk.Label(header, textvariable=self.status).pack(side='left')
        self.button(header, 'Conectar', self.connect)
        form = ttk.LabelFrame(main, text='Leitura do sensor', padding=10)
        form.pack(fill='x', pady=8)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)
        self.field(form, 'Sensor:', self.sensor, 0, 0, span=3)
        self.field(form, 'Data/hora UTC:', self.when, 1, 0)
        self.field(form, 'Calibração:', self.calibration, 1, 2, width=12)
        self.field(form, 'Temperatura (°C):', self.temp, 2, 0)
        self.field(form, 'Umidade (%):', self.humidity, 2, 2, width=12)
        actions = ttk.Frame(form)
        actions.grid(row=3, column=0, columnspan=4, sticky='w')
        for label, command in [('Inserir', self.insert), ('Atualizar calibração', self.calibrate), ('Excluir leitura', self.delete), ('Novo sensor', self.new_sensor), ('Data atual', lambda: self.when.set(date_text(datetime.now(UTC))))]:
            self.button(actions, label, command)

        query = ttk.LabelFrame(main, text='Consulta do sensor acima por intervalo (UTC)', padding=10)
        query.pack(fill='x', pady=(0, 8))
        query.columnconfigure(1, weight=1)
        query.columnconfigure(3, weight=1)
        self.field(query, 'Início:', self.start, 0, 0)
        self.field(query, 'Fim:', self.end, 0, 2)
        actions = ttk.Frame(query)
        actions.grid(row=1, column=0, columnspan=4, sticky='w')
        self.button(actions, 'Consultar (monitor)', self.read)
        self.button(actions, 'Testar SELECT do ingestor', self.permissions)

        simulation = ttk.LabelFrame(main, text='Simular envio do sensor acima', padding=10)
        simulation.pack(fill='x', pady=(0, 8))
        ttk.Label(simulation, text='Quantidade:').pack(side='left')
        ttk.Entry(simulation, textvariable=self.count, width=6).pack(side='left', padx=6)
        ttk.Label(simulation, text='Intervalo (s):').pack(side='left')
        ttk.Entry(simulation, textvariable=self.delay, width=6).pack(side='left', padx=6)
        self.button(simulation, 'Simular', self.simulate)
        self.stop_button = ttk.Button(simulation, text='Parar', command=self.stop.set, state='disabled')
        self.stop_button.pack(side='left', padx=4)

        table = ttk.Frame(main)
        table.pack(fill='both', expand=True)
        self.table = ttk.Treeview(table, columns=('sensor', 'when', 'temp', 'humidity', 'calibration'), show='headings', height=7)
        for name, label, width in [('sensor', 'Sensor', 230), ('when', 'Data/hora UTC', 205), ('temp', 'Temp. °C', 95), ('humidity', 'Umidade %', 95), ('calibration', 'Calibração', 95)]:
            self.table.heading(name, text=label)
            self.table.column(name, width=width, minwidth=70)
        bar = ttk.Scrollbar(table, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=bar.set)
        self.table.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')
        self.table.bind('<<TreeviewSelect>>', self.select_row)
        ttk.Label(main, text='Selecione uma linha para preencher os campos. Datas: AAAA-MM-DD HH:MM:SS.mmm, em UTC.').pack(anchor='w', pady=4)
        self.output = ScrolledText(main, height=4, state='disabled', wrap='word')
        self.output.pack(fill='x')

    def refresh_status(self):
        mode = 'DEMO - sem banco' if self.settings.mode == 'demo' else 'Cassandra real'
        self.status.set(f'{mode} | {"Conectado" if self.connected else "Desconectado"}    ')

    def log(self, text):
        self.output.configure(state='normal')
        self.output.insert('end', text + '\n')
        self.output.see('end')
        self.output.configure(state='disabled')

    def error(self, text):
        self.log(text)
        if not self.closing:
            messagebox.showerror('Erro', text, parent=self)

    def work(self, task, done, *, connection=True):
        if self.busy or self.closing:
            return
        if connection and not self.connected:
            self.error('Conecte antes de executar a operação.')
            return
        self.busy = True
        for button in self.buttons:
            button.configure(state='disabled')

        def worker():
            try:
                self.events.put(('done', done, task()))
            except TelemetryError as error:
                self.events.put(('error', str(error), isinstance(error, (AuthenticationFailure, ConnectionFailure))))
            except Exception:
                self.events.put(('error', 'Não foi possível concluir a operação. Verifique a configuração.', False))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                item = self.events.get_nowait()
                if item[0] == 'progress':
                    self.when.set(date_text(item[1].data_hora))
                    self.log(f'Enviada {item[2]}/{item[3]}: {date_text(item[1].data_hora)} UTC')
                    continue
                self.busy = False
                for button in self.buttons:
                    button.configure(state='normal')
                self.stop_button.configure(state='disabled')
                if item[0] == 'done':
                    item[1](item[2])
                    if self.destroyed:
                        return
                else:
                    if item[2]:
                        self.connected = False
                        self.refresh_status()
                    self.error(item[1])
        except queue.Empty:
            pass
        if not self.destroyed:
            self.after(80, self.poll)

    def connect(self):
        self.connected = False
        self.refresh_status()

        def done(_):
            self.connected = True
            self.refresh_status()
            self.log('Conexão pronta para uso.')
        self.work(self.repo.connect, done, connection=False)

    def new_sensor(self):
        self.sensor.set(self.unique_sensor())
        self.when.set(date_text(datetime.now(UTC)))

    def insert(self):
        try:
            row = new_reading(self.sensor.get(), self.temp.get(), self.humidity.get(), self.calibration.get(), timestamp(self.when.get()))
        except TelemetryError as error:
            self.error(str(error))
            return
        self.work(lambda: self.repo.insert(row), lambda _: self.log('Leitura inserida. Use Consultar para conferir.'))

    def query_values(self):
        sensor = sensor_name(self.sensor.get())
        start, end = timestamp(self.start.get()), timestamp(self.end.get())
        validate_interval(start, end)
        return sensor, start, end

    def show_rows(self, result):
        self.rows = result.rows
        self.table.delete(*self.table.get_children())
        for i, row in enumerate(result.rows):
            self.table.insert('', 'end', iid=str(i), values=(row.sensor_id, date_text(row.data_hora), *['-' if v is None else f'{v:.1f}' for v in (row.temperatura, row.umidade, row.calibracao)]))
        self.log(f'{len(result.rows)} leitura(s) retornada(s), em ordem cronológica.' + (' Limite de 500: reduza o intervalo.' if result.truncated else ''))

    def read(self):
        try:
            values = self.query_values()
        except TelemetryError as error:
            self.error(str(error))
            return
        self.work(lambda: self.repo.read(*values), self.show_rows)

    def select_row(self, event=None):
        selection = self.table.selection()
        if not selection:
            return
        row = self.rows[int(selection[0])]
        self.sensor.set(row.sensor_id)
        self.when.set(date_text(row.data_hora))
        self.temp.set('' if row.temperatura is None else str(row.temperatura))
        self.humidity.set('' if row.umidade is None else str(row.umidade))
        self.calibration.set('0' if row.calibracao is None else str(row.calibracao))

    def change(self, delete=False):
        try:
            sensor, when = sensor_name(self.sensor.get()), timestamp(self.when.get())
            value = None if delete else number(self.calibration.get(), 'Calibração')
        except TelemetryError as error:
            self.error(str(error))
            return
        operation = 'Excluir esta leitura' if delete else 'Atualizar a calibração'
        extra = '' if delete else '\nUPDATE pode criar uma linha parcial se a chave não existir (upsert).'
        if not messagebox.askyesno('Confirmar', f'{operation}?\n{sensor}\n{date_text(when)} UTC{extra}', parent=self):
            return
        task = (lambda: self.repo.delete(sensor, when)) if delete else (lambda: self.repo.calibrate(sensor, when, value))
        self.work(task, lambda _: self.log('DELETE concluído. Consulte para confirmar a ausência.' if delete else 'UPDATE concluído. Consulte para conferir a calibração.'))

    def calibrate(self):
        self.change()

    def delete(self):
        self.change(delete=True)

    def permissions(self):
        try:
            values = self.query_values()
        except TelemetryError as error:
            self.error(str(error))
            return

        def task():
            try:
                self.repo.read(*values, role='ingestor', limit=1)
            except PermissionDenied:
                text = 'Bloqueio SIMULADO do SELECT do ingestor.' if self.settings.mode == 'demo' else 'Cassandra negou SELECT ao ingestor, conforme esperado.'
            else:
                text = 'SELECT permitido ao ingestor. Revise as permissões no banco.'
            return text, self.repo.read(*values)

        def done(result):
            self.log(result[0] + ' Consulta abaixo usa o monitor.')
            self.show_rows(result[1])
        self.work(task, done)

    def simulate(self):
        try:
            sensor = sensor_name(self.sensor.get())
            count, delay = simulation_parameters(self.count.get(), self.delay.get())
        except TelemetryError as error:
            self.error(str(error))
            return
        self.stop.clear()

        def task():
            sent = 0
            for i in range(count):
                if self.stop.is_set():
                    break
                row = simulated_reading(sensor)
                self.repo.insert(row)
                sent += 1
                self.events.put(('progress', row, sent, count))
                if i < count - 1 and self.stop.wait(delay):
                    break
            return sent
        self.work(task, lambda sent: self.log(f'Envio encerrado: {sent} leituras confirmadas.'))
        if self.busy:
            self.stop_button.configure(state='normal')

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.stop.set()
        self.wait_close()

    def wait_close(self):
        if self.busy:
            self.after(100, self.wait_close)
        else:
            self.closing = False
            self.work(self.repo.close, lambda _: self.destroy(), connection=False)
            self.closing = True

    def destroy(self):
        self.destroyed = True
        self.stop.set()
        for token in self.tk.call('after', 'info'):
            self.after_cancel(token)
        super().destroy()
