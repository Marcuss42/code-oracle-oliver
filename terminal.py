from ai.agent.agent import executar_agente
from ai.repository.repository import carregar_repositorios
from ai.analyzer.storage import tem_conhecimento


print("=" * 70)
print("ORÁCULO DE CÓDIGO")
print("=" * 70)

repositorios = carregar_repositorios()

for repo in repositorios:
    if tem_conhecimento(repo["nome"]):
        print(
            f"Já tenho conhecimento de: {repo['nome']}"
        )

print(
    "\nPode me perguntar sobre o código normalmente."
)

print(
    "Para refazer a análise completa, diga algo como "
    "'analise tudo novamente'."
)

print(
    "Para gerar um relatório, diga "
    "'gere um relatório'."
)

print(
    "Digite 'sair' para encerrar.\n"
)

while True:

    mensagem = input("Você: ").strip()

    if not mensagem:
        continue

    if mensagem.casefold() in {
        "sair",
        "exit",
        "quit"
    }:
        break

    try:
        resposta = executar_agente(
            mensagem
        )

        print(
            f"\nOráculo: {resposta}\n"
        )

    except KeyboardInterrupt:
        print("\nEncerrado.")
        break

    except Exception as erro:
        print(
            f"\nErro: {erro}\n"
        )