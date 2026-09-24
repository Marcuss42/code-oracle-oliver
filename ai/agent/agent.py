import json
import time

from ai.config.logger import logger, registrar_tool, registrar_erro, registrar_modelo
from ai.config.config import client, MODEL, PRECOS, config
from ai.agent.state import EstadoAgente
from ai.repository.repository import carregar_repositorios
from ai.analyzer.storage import carregar_index, carregar_conhecimento
from ai.tool.tools import TOOL_DEFINITIONS, TOOLS


estado = EstadoAgente()


MAX_HISTORICO = config.getint("agente", "max_historico", fallback=10)
MAX_RODADAS_TOOLS = config.getint("agente", "max_rodadas_tools", fallback=8)
MAX_CATALOGO_CHARS = config.getint("agente", "max_catalogo_chars", fallback=16000)


def carregar_regras() -> str:
    arquivos = [
        "ai/agent/rules/behavior.txt",
        "ai/agent/rules/analysis.txt",
        "ai/agent/rules/conversation.txt"
    ]

    partes = []

    for arquivo in arquivos:
        with open(arquivo, encoding="utf-8") as f:
            partes.append(f.read())

    return "\n\n".join(partes)


SYSTEM_PROMPT = carregar_regras()


def criar_catalogo() -> str:
    partes = []

    for repo in carregar_repositorios():
        nome_repo = repo["nome"]
        index = carregar_index(nome_repo)
        conhecimento = carregar_conhecimento(nome_repo)

        partes.append(f"REPOSITÓRIO: {nome_repo}")
        partes.append(f"PATH: {repo['path']}")

        if conhecimento:
            partes.append("CONHECIMENTO GERAL:")
            partes.append(conhecimento)

        arquivos = index.get("arquivos", [])

        if arquivos:
            partes.append("ARQUIVOS COM CONHECIMENTO ARMAZENADO:")

            for arquivo in arquivos:
                partes.append(
                    json.dumps(
                        {
                            "arquivo": arquivo.get("arquivo"),
                            "funcao": arquivo.get("funcao"),
                            "path": arquivo.get("path")
                        },
                        ensure_ascii=False,
                        separators=(",", ":")
                    )
                )

    catalogo = "\n".join(partes)

    if not catalogo:
        return "(Nenhum conhecimento armazenado.)"

    if len(catalogo) <= MAX_CATALOGO_CHARS:
        return catalogo

    return "[CATÁLOGO PARCIAL]\n" + catalogo[:MAX_CATALOGO_CHARS]


def mensagem_assistente(message) -> dict:
    tool_calls = []

    for tool_call in message.tool_calls or []:
        nome = tool_call.function.name.split("<|channel|>", 1)[0]

        tool_calls.append(
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": nome,
                    "arguments": tool_call.function.arguments
                }
            }
        )

    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": tool_calls
    }


def calcular_custo(response) -> tuple[int, float]:
    usage = response.usage
    detalhes = getattr(usage, "prompt_tokens_details", None)
    cached_tokens = getattr(detalhes, "cached_tokens", 0) or 0
    preco = PRECOS.get(MODEL)

    if not preco:
        return cached_tokens, 0.0

    prompt_tokens = usage.prompt_tokens
    completion_tokens = usage.completion_tokens
    entrada = max(prompt_tokens - cached_tokens, 0)

    custo = (
        entrada / 1_000_000 * preco["entrada"]
        + cached_tokens / 1_000_000 * preco["entrada_cache"]
        + completion_tokens / 1_000_000 * preco["saida"]
    )

    return cached_tokens, custo


def executar_tool(nome: str, argumentos: dict) -> str:
    nome = nome.split("<|channel|>", 1)[0]
    funcao = TOOLS.get(nome)

    if funcao is None:
        registrar_erro(f"Ferramenta desconhecida: {nome}")
        return f"Ferramenta desconhecida: {nome}"

    inicio = time.perf_counter()

    logger.info(
        "TOOL | iniciando=%s | argumentos=%s",
        nome,
        argumentos
    )

    try:
        resultado = str(funcao(**argumentos))

        registrar_tool(
            nome,
            time.perf_counter() - inicio,
            True
        )

        return resultado

    except Exception as erro:
        registrar_tool(
            nome,
            time.perf_counter() - inicio,
            False
        )
        registrar_erro(f"Tool {nome}: {erro}")
        raise


def executar_agente(mensagem: str) -> str:
    estado.adicionar_mensagem("user", mensagem)

    mensagens = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "system",
            "content": "CATÁLOGO ATUAL DO CONHECIMENTO:\n" + criar_catalogo()
        },
        *estado.mensagens[-MAX_HISTORICO:]
    ]

    for _ in range(MAX_RODADAS_TOOLS):
        inicio = time.perf_counter()

        response = client.chat.completions.create(
            model=MODEL,
            messages=mensagens,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            parallel_tool_calls=False,
            reasoning_effort="low",
            max_completion_tokens=2048
        )

        cached_tokens, custo = calcular_custo(response)

        registrar_modelo(
            MODEL,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.usage.total_tokens,
            cached_tokens,
            time.perf_counter() - inicio,
            custo
        )

        message = response.choices[0].message

        if not message.tool_calls:
            resposta = (message.content or "").strip()
            estado.adicionar_mensagem("assistant", resposta)
            return resposta

        mensagens.append(mensagem_assistente(message))

        for tool_call in message.tool_calls:
            nome = tool_call.function.name.split("<|channel|>", 1)[0]

            try:
                argumentos = json.loads(
                    tool_call.function.arguments or "{}"
                )
            except json.JSONDecodeError:
                resultado = "Argumentos inválidos enviados para a ferramenta."
            else:
                resultado = executar_tool(nome, argumentos)

            mensagens.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": resultado
                }
            )

    resposta = "Não consegui concluir a análise."
    estado.adicionar_mensagem("assistant", resposta)
    return resposta