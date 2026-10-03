#!/usr/bin/env python3
"""
JARVIS v4.2 Android
Assistente local + Gemini, tarefas, finanças, memória e pesquisa web.
"""

from __future__ import annotations

import ast
import json
import re
import threading
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.textinput import TextInput


KV = r"""
#:import dp kivy.metrics.dp

<JarvisMainScreen>:
    BoxLayout:
        orientation: "vertical"
        canvas.before:
            Color:
                rgba: .02, .04, .08, 1
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12), dp(6)
            spacing: dp(8)
            canvas.before:
                Color:
                    rgba: .06, .10, .16, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Label:
                text: "JARVIS v4.2"
                color: 0, .85, 1, 1
                font_size: "18sp"
                bold: True
                halign: "left"
                valign: "middle"
                text_size: self.size

            Button:
                text: "CONFIG"
                size_hint_x: None
                width: dp(82)
                font_size: "11sp"
                background_normal: ""
                background_color: .12, .20, .30, 1
                on_release: app.open_config_popup()

        BoxLayout:
            size_hint_y: None
            height: dp(32)
            padding: dp(10), dp(4)
            canvas.before:
                Color:
                    rgba: .04, .07, .12, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Label:
                id: status_label
                text: "SISTEMA LOCAL | PRONTO"
                color: .2, .9, .5, 1
                font_size: "10sp"
                bold: True
                halign: "left"
                valign: "middle"
                text_size: self.size

        ScrollView:
            id: scroll
            do_scroll_x: False
            bar_width: dp(4)

            BoxLayout:
                id: chat_container
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: dp(10)
                spacing: dp(8)

        BoxLayout:
            size_hint_y: None
            height: dp(62)
            padding: dp(8)
            spacing: dp(8)
            canvas.before:
                Color:
                    rgba: .06, .10, .16, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            TextInput:
                id: user_input
                hint_text: "Digite um comando..."
                multiline: False
                font_size: "15sp"
                foreground_color: 1, 1, 1, 1
                background_color: .10, .15, .22, 1
                cursor_color: 0, .85, 1, 1
                padding: dp(10), dp(10)
                on_text_validate: app.send_message()

            Button:
                text: "EXEC"
                size_hint_x: None
                width: dp(78)
                font_size: "13sp"
                bold: True
                background_normal: ""
                background_color: 0, .60, .85, 1
                on_release: app.send_message()

        BoxLayout:
            size_hint_y: None
            height: dp(46)
            padding: dp(4)
            spacing: dp(4)
            canvas.before:
                Color:
                    rgba: .03, .05, .09, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

            Button:
                text: "Ajuda"
                font_size: "10sp"
                background_normal: ""
                background_color: .08, .14, .22, 1
                on_release: app.quick_command("ajuda")

            Button:
                text: "Tarefas"
                font_size: "10sp"
                background_normal: ""
                background_color: .08, .14, .22, 1
                on_release: app.quick_command("tarefas")

            Button:
                text: "Finanças"
                font_size: "10sp"
                background_normal: ""
                background_color: .08, .14, .22, 1
                on_release: app.quick_command("resumo financeiro")

            Button:
                text: "Memória"
                font_size: "10sp"
                background_normal: ""
                background_color: .08, .14, .22, 1
                on_release: app.quick_command("mostrar memória")

            Button:
                text: "Status"
                font_size: "10sp"
                background_normal: ""
                background_color: .08, .14, .22, 1
                on_release: app.quick_command("status")
"""


class SafeCalculator:
    OPERATORS = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b,
        ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a ** b,
    }

    UNARY = {
        ast.UAdd: lambda a: +a,
        ast.USub: lambda a: -a,
    }

    @classmethod
    def evaluate(cls, expression: str):
        expression = expression.replace("^", "**").strip()
        if not expression:
            raise ValueError("Expressão vazia.")

        if len(expression) > 120:
            raise ValueError("Expressão muito longa.")

        tree = ast.parse(expression, mode="eval")
        result = cls._eval(tree.body)

        if isinstance(result, (int, float)):
            if not (-10**100 < result < 10**100):
                raise ValueError("Resultado fora do limite.")
        return result

    @classmethod
    def _eval(cls, node):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        ):
            return node.value

        if isinstance(node, ast.UnaryOp) and type(node.op) in cls.UNARY:
            return cls.UNARY[type(node.op)](cls._eval(node.operand))

        if isinstance(node, ast.BinOp) and type(node.op) in cls.OPERATORS:
            left = cls._eval(node.left)
            right = cls._eval(node.right)

            if isinstance(node.op, ast.Pow):
                if abs(right) > 100:
                    raise ValueError("Expoente acima do limite de segurança.")
                if left == 0 and right < 0:
                    raise ValueError("Divisão por zero.")

            return cls.OPERATORS[type(node.op)](left, right)

        raise ValueError("Operação não suportada.")


class AutonomousJarvisEngine:
    def __init__(self, app_data_dir: str):
        self.base_path = Path(app_data_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.db_file = self.base_path / "jarvis_data.json"
        self.config_file = self.base_path / "jarvis_config.json"

        self.data = self.load_data()
        self.config = self.load_config()

    @staticmethod
    def _default_data():
        return {
            "learned": {},
            "tasks": [],
            "finances": [],
            "conversation": [],
        }

    @staticmethod
    def _default_config():
        return {
            "api_key": "",
            "model": "gemini-2.5-flash",
            "autonomous_mode": True,
        }

    def load_data(self):
        data = self._default_data()
        try:
            if self.db_file.exists():
                loaded = json.loads(self.db_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    for key in data:
                        if key in loaded:
                            data[key] = loaded[key]
        except Exception:
            pass
        return data

    def load_config(self):
        config = self._default_config()
        try:
            if self.config_file.exists():
                loaded = json.loads(self.config_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    config.update(loaded)
        except Exception:
            pass
        return config

    def save_config(self):
        self._atomic_write(self.config_file, self.config)

    def save_data(self):
        self._atomic_write(self.db_file, self.data)

    @staticmethod
    def _atomic_write(path: Path, data: dict):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(path.suffix + ".tmp")
            temp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp.replace(path)
        except Exception as exc:
            print(f"Falha ao salvar {path.name}: {exc}")

    @staticmethod
    def parse_brazilian_number(value: str) -> float:
        value = value.strip().replace("R$", "").replace(" ", "")
        if "," in value and "." in value:
            value = value.replace(".", "").replace(",", ".")
        elif "," in value:
            value = value.replace(",", ".")
        return float(value)

    def execute_tool(self, tool_name: str, args: dict) -> str:
        try:
            if tool_name == "calculator":
                result = SafeCalculator.evaluate(args.get("expression", ""))
                return f"🧮 Resultado: {result}"

            if tool_name == "add_task":
                title = str(args.get("title", "")).strip()
                if not title:
                    return "❌ Título de tarefa vazio."

                ids = [
                    int(t.get("id", 0))
                    for t in self.data["tasks"]
                    if str(t.get("id", "")).isdigit()
                ]
                task_id = max(ids or [0]) + 1

                self.data["tasks"].append(
                    {
                        "id": task_id,
                        "text": title,
                        "done": False,
                        "created_at": datetime.now().isoformat(),
                    }
                )
                self.save_data()
                return f"✅ Tarefa #{task_id} criada: {title}"

            if tool_name == "complete_task":
                task_id = int(args.get("id", 0))
                for task in self.data["tasks"]:
                    if int(task.get("id", 0)) == task_id:
                        task["done"] = True
                        self.save_data()
                        return f"✅ Tarefa #{task_id} concluída."
                return f"❌ Tarefa #{task_id} não encontrada."

            if tool_name == "add_finance":
                amount = self.parse_brazilian_number(str(args.get("amount", "0")))
                if amount < 0:
                    raise ValueError("O valor deve ser positivo.")

                finance_type = args.get("type", "expense")
                if finance_type not in {"income", "expense"}:
                    finance_type = "expense"

                category = str(args.get("category", "Geral")).strip() or "Geral"

                self.data["finances"].append(
                    {
                        "type": finance_type,
                        "amount": amount,
                        "category": category,
                        "date": datetime.now().strftime("%d/%m/%Y"),
                    }
                )
                self.save_data()

                tag = "💰 Receita" if finance_type == "income" else "💸 Despesa"
                return f"{tag}: R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + f" ({category})"

            if tool_name == "save_memory":
                info = str(args.get("info", "")).strip()
                if not info:
                    return "❌ Memória vazia."

                key = f"memo_{len(self.data['learned']) + 1}"
                self.data["learned"][key] = info
                self.save_data()
                return f"🧠 Memória guardada: {info}"

            if tool_name == "web_search":
                return self._web_search(str(args.get("query", "")).strip())

            return f"❌ Ferramenta desconhecida: {tool_name}"

        except Exception as exc:
            return f"❌ Erro em {tool_name}: {exc}"

    def call_gemini_api(self, prompt: str) -> str:
        api_key = str(self.config.get("api_key", "")).strip()
        if not api_key:
            return ""

        model = str(self.config.get("model", "gemini-2.5-flash")).strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
            model = "gemini-2.5-flash"

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={urllib.parse.quote(api_key)}"
        )

        system_prompt = (
            "Você é JARVIS, um assistente pessoal em português do Brasil. "
            "Responda de forma direta, útil, organizada e objetiva. "
            "Não invente fatos. Quando não souber, diga que não sabe."
        )

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 1200,
            },
        }

        try:
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "JARVIS-Android/4.2",
                },
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))

            candidates = result.get("candidates", [])
            if not candidates:
                return ""

            parts = candidates[0].get("content", {}).get("parts", [])
            texts = [
                str(part.get("text", ""))
                for part in parts
                if part.get("text")
            ]
            return "\n".join(texts).strip()

        except Exception as exc:
            print(f"Gemini: {exc}")
            return ""

    def process_input(self, user_text: str) -> str:
        command = user_text.strip()
        if not command:
            return ""

        self.data["conversation"].append(
            {
                "role": "user",
                "text": command,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self.data["conversation"] = self.data["conversation"][-100:]
        self.save_data()

        lower = command.lower()
        actions = []

        if lower in {"ajuda", "help", "comandos"}:
            return (
                "🤖 JARVIS v4.2\n\n"
                "⚡ Comandos:\n"
                "• calcule 120 / 4\n"
                "• tarefa estudar matemática\n"
                "• concluir tarefa 1\n"
                "• gastei 50 no almoço\n"
                "• recebi 150 de salário\n"
                "• resumo financeiro\n"
                "• lembre que minha prova é sexta\n"
                "• mostrar memória\n"
                "• pesquise notícias sobre tecnologia\n"
                "• status\n\n"
                "Você também pode escrever perguntas normais com a API Gemini conectada."
            )

        expense_pattern = re.compile(
            r"(?:gastei|gasto|despesa)\s+R?\$?\s*"
            r"(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
            r"(?:\s+(?:em|com|no|na|de)\s+([^,;.!?]+))?",
            re.IGNORECASE,
        )
        income_pattern = re.compile(
            r"(?:recebi|ganho|ganhei|receita)\s+R?\$?\s*"
            r"(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
            r"(?:\s+(?:de|com|no|na)\s+([^,;.!?]+))?",
            re.IGNORECASE,
        )

        expense = expense_pattern.search(command)
        if expense:
            category = expense.group(2).strip() if expense.group(2) else "Geral"
            actions.append(
                self.execute_tool(
                    "add_finance",
                    {
                        "type": "expense",
                        "amount": expense.group(1),
                        "category": category,
                    },
                )
            )

        income = income_pattern.search(command)
        if income:
            category = income.group(2).strip() if income.group(2) else "Geral"
            actions.append(
                self.execute_tool(
                    "add_finance",
                    {
                        "type": "income",
                        "amount": income.group(1),
                        "category": category,
                    },
                )
            )

        complete = re.search(
            r"(?:concluir|finalizar|terminar)\s+tarefa\s+(\d+)",
            lower,
        )
        if complete:
            actions.append(
                self.execute_tool(
                    "complete_task",
                    {"id": complete.group(1)},
                )
            )

        task = re.search(
            r"(?:adicionar\s+tarefa|tarefa|lembrar\s+de)\s*:?\s*(.+)$",
            command,
            re.IGNORECASE,
        )
        if task and not lower.startswith("lembre"):
            task_text = task.group(1).strip()
            if task_text:
                actions.append(
                    self.execute_tool(
                        "add_task",
                        {"title": task_text},
                    )
                )

        calc = re.search(
            r"(?:calcule|quanto\s+(?:é|e|dá|da))\s+"
            r"([0-9+\-*/().^ \t]+)",
            lower,
        )
        if calc:
            actions.append(
                self.execute_tool(
                    "calculator",
                    {"expression": calc.group(1).strip()},
                )
            )

        if actions:
            return "⚡ EXECUÇÃO:\n" + "\n".join(actions)

        if lower in {"tarefas", "listar tarefas"}:
            pending = [
                task for task in self.data["tasks"]
                if not task.get("done", False)
            ]
            if not pending:
                return "📋 Nenhuma tarefa pendente."

            return "📋 TAREFAS PENDENTES\n" + "\n".join(
                f"#{task['id']} — {task['text']}" for task in pending
            )

        if "resumo financeiro" in lower or lower in {"finanças", "financas"}:
            income = sum(
                float(item.get("amount", 0))
                for item in self.data["finances"]
                if item.get("type") == "income"
            )
            expense = sum(
                float(item.get("amount", 0))
                for item in self.data["finances"]
                if item.get("type") == "expense"
            )
            balance = income - expense

            def brl(value):
                return (
                    f"R$ {value:,.2f}"
                    .replace(",", "X")
                    .replace(".", ",")
                    .replace("X", ".")
                )

            return (
                "💰 RESUMO FINANCEIRO\n"
                f"🟢 Receitas: {brl(income)}\n"
                f"🔴 Despesas: {brl(expense)}\n"
                f"⚖️ Saldo: {brl(balance)}"
            )

        if lower.startswith("lembre"):
            info = re.sub(
                r"^lembre(?:\s+que)?\s*",
                "",
                command,
                flags=re.IGNORECASE,
            ).strip()
            return self.execute_tool("save_memory", {"info": info})

        if "mostrar memória" in lower or "mostrar memoria" in lower or lower == "memoria":
            if not self.data["learned"]:
                return "🧠 Nenhuma memória guardada."
            return "🧠 MEMÓRIAS\n" + "\n".join(
                f"• {value}" for value in self.data["learned"].values()
            )

        if lower == "status":
            pending = sum(
                1 for task in self.data["tasks"]
                if not task.get("done", False)
            )
            connected = bool(self.config.get("api_key"))
            return (
                "📊 STATUS JARVIS\n"
                f"• Gemini: {'conectado' if connected else 'offline'}\n"
                f"• Modelo: {self.config.get('model', 'gemini-2.5-flash')}\n"
                f"• Tarefas pendentes: {pending}\n"
                f"• Memórias: {len(self.data['learned'])}\n"
                f"• Registros financeiros: {len(self.data['finances'])}\n"
                f"• Conversas armazenadas: {len(self.data['conversation'])}"
            )

        if re.match(r"^(pesquise|buscar|procure)\b", lower):
            query = re.sub(
                r"^(pesquise|buscar|procure)\s*",
                "",
                command,
                flags=re.IGNORECASE,
            ).strip()
            return self.execute_tool("web_search", {"query": query})

        gemini = self.call_gemini_api(command)
        if gemini:
            return f"🤖 JARVIS:\n\n{gemini}"

        return (
            "🤖 JARVIS LOCAL:\n"
            "Comando não reconhecido.\n\n"
            "Digite 'ajuda' para ver os comandos locais ou conecte a API Gemini em CONFIG."
        )

    def _web_search(self, query: str) -> str:
        if not query:
            return "🔎 Informe o que deseja pesquisar."

        try:
            url = (
                "https://html.duckduckgo.com/html/?q="
                + urllib.parse.quote_plus(query)
            )

            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 JARVIS/4.2"},
            )

            with urllib.request.urlopen(request, timeout=10) as response:
                html = response.read().decode("utf-8", "ignore")

            matches = re.findall(
                r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                html,
                flags=re.IGNORECASE | re.DOTALL,
            )

            if not matches:
                return "🔎 Nenhum resultado encontrado."

            lines = ["🔎 PESQUISA WEB"]
            for index, (link, title) in enumerate(matches[:5], 1):
                clean_title = re.sub(r"<.*?>", "", title)
                clean_title = (
                    clean_title.replace("&amp;", "&")
                    .replace("&quot;", '"')
                    .strip()
                )
                lines.append(f"{index}. {clean_title}\n{link}")

            return "\n\n".join(lines)

        except Exception:
            return "🌐 Não foi possível realizar a pesquisa agora."


class JarvisMainScreen(Screen):
    pass


class JarvisApp(App):
    def build(self):
        self.title = "JARVIS"
        self.engine = AutonomousJarvisEngine(self.user_data_dir)

        Builder.load_string(KV)

        manager = ScreenManager()
        manager.add_widget(JarvisMainScreen(name="main"))

        Clock.schedule_once(
            lambda _: self.add_message_bubble(
                "🤖 JARVIS v4.2 iniciado.\n"
                "Sistema local pronto. Use 'ajuda' para começar.",
                is_user=False,
            ),
            0.2,
        )
        return manager

    def set_status(self, text: str):
        try:
            self.root.get_screen("main").ids.status_label.text = text
        except Exception:
            pass

    def add_message_bubble(self, text: str, is_user: bool = False):
        screen = self.root.get_screen("main")
        container = screen.ids.chat_container

        prefix = "VOCÊ: " if is_user else ""
        label = Label(
            text=prefix + text,
            color=(1, 1, 1, 1) if is_user else (0.85, 0.95, 1, 1),
            font_size="14sp",
            size_hint_y=None,
            halign="left",
            valign="top",
            padding=(dp(12), dp(10)),
        )

        def update_label(instance, width):
            instance.text_size = (max(width - dp(24), dp(120)), None)
            instance.height = instance.texture_size[1] + dp(20)

        label.bind(width=update_label)
        container.add_widget(label)

        Clock.schedule_once(
            lambda _: setattr(screen.ids.scroll, "scroll_y", 0),
            0.05,
        )

    def send_message(self):
        screen = self.root.get_screen("main")
        input_box = screen.ids.user_input
        command = input_box.text.strip()

        if not command:
            return

        input_box.text = ""
        self.add_message_bubble(command, is_user=True)
        self.set_status("PROCESSANDO...")

        def worker():
            response = self.engine.process_input(command)

            Clock.schedule_once(
                lambda _: (
                    self.add_message_bubble(response, is_user=False),
                    self.set_status(
                        "GEMINI CONECTADO | PRONTO"
                        if self.engine.config.get("api_key")
                        else "MODO LOCAL | PRONTO"
                    ),
                ),
                0,
            )

        threading.Thread(target=worker, daemon=True).start()

    def quick_command(self, command: str):
        screen = self.root.get_screen("main")
        screen.ids.user_input.text = command
        self.send_message()

    def open_config_popup(self):
        box = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(10),
        )

        box.add_widget(
            Label(
                text="Chave da API Gemini",
                size_hint_y=None,
                height=dp(30),
            )
        )

        api_input = TextInput(
            text=self.engine.config.get("api_key", ""),
            multiline=False,
            password=True,
            font_size="13sp",
            size_hint_y=None,
            height=dp(42),
        )
        box.add_widget(api_input)

        box.add_widget(
            Label(
                text="Modelo",
                size_hint_y=None,
                height=dp(30),
            )
        )

        model_input = TextInput(
            text=self.engine.config.get("model", "gemini-2.5-flash"),
            multiline=False,
            font_size="13sp",
            size_hint_y=None,
            height=dp(42),
        )
        box.add_widget(model_input)

        save_button = Button(
            text="SALVAR",
            size_hint_y=None,
            height=dp(44),
            background_normal="",
            background_color=(0, 0.6, 0.8, 1),
        )
        box.add_widget(save_button)

        popup = Popup(
            title="Configurações JARVIS",
            content=box,
            size_hint=(0.92, 0.62),
            auto_dismiss=True,
        )

        def save_and_close(_):
            self.engine.config["api_key"] = api_input.text.strip()
            self.engine.config["model"] = (
                model_input.text.strip() or "gemini-2.5-flash"
            )
            self.engine.save_config()
            popup.dismiss()

            self.set_status(
                "GEMINI CONECTADO | PRONTO"
                if self.engine.config["api_key"]
                else "MODO LOCAL | PRONTO"
            )
            self.add_message_bubble(
                "⚙️ Configuração salva.",
                is_user=False,
            )

        save_button.bind(on_release=save_and_close)
        popup.open()


if __name__ == "__main__":
    JarvisApp().run()
