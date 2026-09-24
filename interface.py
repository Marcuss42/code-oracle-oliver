import sys

from PySide6.QtCore import QEvent, QThread, Signal, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ai.agent.agent import executar_agente
from ai.repository.repository import carregar_repositorios
from ai.analyzer.storage import tem_conhecimento


STYLE = """
QMainWindow {
    background-color: #0f1117;
}

QWidget {
    background-color: #0f1117;
    color: #e6e9ef;
    font-family: "Segoe UI";
}

QLabel#titulo {
    color: #f5f7fa;
    font-size: 20px;
    font-weight: 600;
    padding: 4px 0;
}

QLabel#subtitulo {
    color: #8b93a7;
    font-size: 12px;
    padding-bottom: 8px;
}

QTextBrowser#chat {
    background-color: #151922;
    border: 1px solid #252b38;
    border-radius: 12px;
    padding: 18px;
    selection-background-color: #34415c;
    selection-color: #ffffff;
}

QTextEdit#entrada {
    background-color: #191d27;
    border: 1px solid #303746;
    border-radius: 10px;
    padding: 12px 14px;
    color: #edf0f5;
    font-size: 14px;
    selection-background-color: #34415c;
}

QTextEdit#entrada:focus {
    border: 1px solid #586b91;
}

QTextEdit#entrada:disabled {
    color: #737b8d;
    background-color: #151922;
}

QPushButton#botao {
    background-color: #4f6bed;
    border: none;
    border-radius: 10px;
    color: white;
    font-size: 13px;
    font-weight: 600;
    padding: 0 22px;
    min-width: 85px;
}

QPushButton#botao:hover {
    background-color: #5c78f5;
}

QPushButton#botao:pressed {
    background-color: #435dcc;
}

QPushButton#botao:disabled {
    background-color: #303746;
    color: #737b8d;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0;
}

QScrollBar::handle:vertical {
    background: #343b4b;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #454e61;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}
"""


class Worker(QThread):
    resposta = Signal(str)
    erro = Signal(str)

    def __init__(self, mensagem):
        super().__init__()
        self.mensagem = mensagem

    def run(self):
        try:
            resposta = executar_agente(self.mensagem)
            self.resposta.emit(resposta)
        except Exception as erro:
            self.erro.emit(str(erro))


class JanelaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()

        self.worker = None
        self.conversa = ""

        self.setWindowTitle("CODE ORACLE")
        self.resize(1100, 750)
        self.setMinimumSize(800, 600)

        self.setStyleSheet(STYLE)

        self.criar_interface()
        self.mostrar_informacoes_iniciais()

    def criar_interface(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        titulo = QLabel("CODE ORACLE")
        titulo.setObjectName("titulo")

        subtitulo = QLabel(
            "Análise inteligente de código"
        )
        subtitulo.setObjectName("subtitulo")

        self.chat = QTextBrowser()
        self.chat.setObjectName("chat")
        self.chat.setOpenExternalLinks(True)
        self.chat.setOpenLinks(True)

        fonte = QFont("Segoe UI", 10)
        self.chat.setFont(fonte)

        self.entrada = QTextEdit()
        self.entrada.setObjectName("entrada")
        self.entrada.setPlaceholderText(
            "Pergunte qualquer coisa sobre o código..."
        )
        self.entrada.setFixedHeight(92)

        self.botao = QPushButton("Enviar")
        self.botao.setObjectName("botao")
        self.botao.clicked.connect(self.enviar)

        entrada_layout = QHBoxLayout()
        entrada_layout.setSpacing(10)
        entrada_layout.addWidget(self.entrada, 1)
        entrada_layout.addWidget(self.botao)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addWidget(self.chat, 1)
        layout.addLayout(entrada_layout)

        self.setCentralWidget(central)

        self.entrada.installEventFilter(self)

    def atualizar_chat(self):
        self.chat.setMarkdown(self.conversa)

        barra = self.chat.verticalScrollBar()
        barra.setValue(barra.maximum())

    def adicionar_markdown(self, texto):
        self.conversa += texto + "\n\n"
        self.atualizar_chat()

    def mostrar_informacoes_iniciais(self):
        texto = (
            "# CODE ORACLE\n\n"
            "Faça perguntas sobre os repositórios disponíveis.\n\n\n"
        )

        repositorios = carregar_repositorios()

        if repositorios:
            texto += "### Repositórios no escopo\n\n"

            for repo in repositorios:
                if tem_conhecimento(repo["nome"]):
                    texto += (
                        f"- **{repo['nome']}**\n"
                    )

        self.adicionar_markdown(texto)

    def enviar(self):
        mensagem = self.entrada.toPlainText().strip()

        if not mensagem:
            return

        self.entrada.clear()
        self.entrada.setEnabled(False)
        self.botao.setEnabled(False)

        self.adicionar_markdown(
            f"\n### Você\n\n{mensagem}"
        )

        self.adicionar_markdown(
            "### CODE ORACLE\n\n"
            "*Analisando...*"
        )

        self.worker = Worker(mensagem)

        self.worker.resposta.connect(
            self.receber_resposta
        )

        self.worker.erro.connect(
            self.receber_erro
        )

        self.worker.finished.connect(
            self.finalizar_worker
        )

        self.worker.start()

    def remover_analisando(self):
        marcador = (
            "### CODE ORACLE\n\n"
            "*Analisando...*\n\n"
        )

        if self.conversa.endswith(marcador):
            self.conversa = self.conversa[
                :-len(marcador)
            ]

    def receber_resposta(self, resposta):
        self.remover_analisando()

        self.adicionar_markdown(
            f"### CODE ORACLE\n\n{resposta}"
        )

    def receber_erro(self, erro):
        self.remover_analisando()

        self.adicionar_markdown(
            "### Erro\n\n"
            f"`{erro}`"
        )

    def finalizar_worker(self):
        self.entrada.setEnabled(True)
        self.botao.setEnabled(True)
        self.entrada.setFocus()
        self.worker = None

    def eventFilter(self, obj, event):
        if (
            obj is self.entrada
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key_Return
            and not (
                event.modifiers()
                & Qt.KeyboardModifier.ShiftModifier
            )
        ):
            self.enviar()
            return True

        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.wait()

        event.accept()


def main():
    app = QApplication(sys.argv)

    app.setApplicationName("CODE ORACLE")

    janela = JanelaPrincipal()
    janela.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()