import json
import re
import time
from pathlib import Path

from ai.config.config import client, MODEL, PRECOS, config
from ai.config.logger import logger, registrar_analise, registrar_modelo, registrar_conhecimento
from ai.repository.repository import buscar_repositorio, listar_arquivos, resolver_arquivo, ler_arquivo
from ai.analyzer.storage import salvar_analise, carregar_analises, carregar_analise, adicionar_conhecimento, salvar_index

BATCH_ATE_KB = config.getint("analise", "batch_ate_kb", fallback=3)
BATCH_ATE_10_KB = config.getint("analise", "batch_ate_10_kb", fallback=10)
BATCH_ATE_30_KB = config.getint("analise", "batch_ate_30_kb", fallback=30)
BATCH_MAX_KB = config.getint("analise", "batch_max_kb", fallback=30)
BATCH_MAX_ARQUIVOS_PEQUENOS = config.getint("analise", "batch_max_arquivos_pequenos", fallback=8)
BATCH_MAX_ARQUIVOS_MEDIOS = config.getint("analise", "batch_max_arquivos_medios", fallback=4)
BATCH_MAX_ARQUIVOS_GRANDES = config.getint("analise", "batch_max_arquivos_grandes", fallback=2)
ANALISE_MAX_COMPLETION_TOKENS = config.getint("analise", "analise_max_completion_tokens", fallback=1600)
CORRECAO_MAX_COMPLETION_TOKENS = config.getint("analise", "correcao_max_completion_tokens", fallback=1600)
BATCH_MAX_COMPLETION_TOKENS = config.getint("analise", "batch_max_completion_tokens", fallback=4096)

CAMPOS_ANALISE = {
    "funcao",
    "responsabilidades",
    "dependencias",
    "relacoes",
    "observacoes",
    "arquivos_para_revisar"
}

PROMPT_ANALISE = """
Você é um analisador técnico de código.

Analise EXCLUSIVAMENTE o código real recebido.

OBJETIVO:
Produzir uma análise técnica precisa, útil para construir uma base de conhecimento que permita posteriormente entender o repositório sem reler todos os arquivos.

PRINCÍPIO CENTRAL:
Registre somente informações que realmente ajudam a entender o comportamento, a arquitetura, o fluxo ou as dependências do código.
Não transforme a análise em uma descrição linha por linha do arquivo.

PRIORIDADE DAS INFORMAÇÕES:
1. Fluxo de execução e comportamento relevante.
2. Relações reais com outros componentes.
3. Persistência, banco, APIs, mensageria e integrações externas.
4. Regras de negócio, condições e transformações relevantes.
5. Configurações e efeitos colaterais importantes.
6. Estruturas internas necessárias para compreender o funcionamento.
7. Boilerplate, imports, getters, setters, anotações e detalhes óbvios: normalmente ignore.

REGRAS:
- Nunca invente informações, arquivos, dependências, relações ou comportamentos.
- O código real tem prioridade sobre qualquer inferência.
- Nomes de classes, métodos, variáveis, pacotes ou imports não provam comportamento por si só.
- Identifique somente relações sustentadas diretamente pelo código.
- Seja específico e técnico.
- Não descreva cada método individualmente quando isso não acrescentar entendimento.
- Não liste imports individualmente como dependências.
- Não liste classes padrão de framework somente porque foram importadas ou anotadas.
- Em dependencias, registre somente componentes realmente relevantes para o funcionamento.
- Em relacoes, registre chamadas, implementações, heranças, acesso a serviços, persistência, APIs, filas ou outras relações efetivamente sustentadas pelo código.
- Em responsabilidades, resuma o papel real do arquivo.
- Em observacoes, registre somente fatos relevantes, problemas evidentes, comportamentos não óbvios ou detalhes arquiteturais importantes.
- Não repita a mesma informação em vários campos.
- Não preencha campos apenas para completar o formato.
- Prefira poucos itens relevantes a listas extensas.
- Como regra, tente manter responsabilidades, dependencias, relacoes e observacoes curtas; ultrapasse isso somente quando houver informação realmente necessária.
- Use [] quando não houver informações relevantes.
- Use "" quando não for possível determinar um valor textual.
- Não invente caminhos de arquivos.
- arquivos_para_revisar deve conter somente arquivos que realmente precisam ser analisados para entender uma relação importante identificada no arquivo atual.
- Só indique um item em arquivos_para_revisar quando o arquivo alvo puder ser identificado com segurança pelo código recebido.
- Cada item de arquivos_para_revisar deve usar:
  {"repositorio":"nome-do-repositorio","arquivo":"caminho/relativo/do/arquivo"}
- Se não for possível determinar com segurança o caminho relativo do arquivo alvo, use [].

ANÁLISE EM LOTE:
Cada arquivo deve ser analisado independentemente.
Não use informações de um arquivo para inventar informações sobre outro.
Não faça uma análise superficial de um arquivo somente porque ele está no mesmo lote.
Distribua a saída entre os arquivos de forma equilibrada.
Não gaste grande parte da resposta descrevendo apenas um arquivo.

CAMPOS OBRIGATÓRIOS:
- funcao
- responsabilidades
- dependencias
- relacoes
- observacoes
- arquivos_para_revisar

ANÁLISE INDIVIDUAL:
Retorne diretamente o objeto da análise.

ANÁLISE EM LOTE:
Retorne:
{
  "arquivos": {
    "caminho/do/arquivo1": {
      "funcao": "",
      "responsabilidades": [],
      "dependencias": [],
      "relacoes": [],
      "observacoes": [],
      "arquivos_para_revisar": []
    }
  }
}

Retorne SOMENTE JSON válido.
"""

SCHEMA_ANALISE = """
{
  "funcao": "",
  "responsabilidades": [],
  "dependencias": [],
  "relacoes": [],
  "observacoes": [],
  "arquivos_para_revisar": []
}

Os campos acima são obrigatórios.
Campos adicionais são permitidos somente quando houver informação técnica relevante sustentada pelo código real.
"""

PROMPT_CORRECAO = """
Você é um normalizador de análise técnica de código.

Recebeu código real e uma análise potencialmente inválida.

Corrija somente problemas de formato, estrutura ou inconsistências evidentes.
Não invente informações.
Preserve informações válidas.
Use o código real somente para corrigir erros evidentes.
Não aumente desnecessariamente a análise durante a correção.
Não adicione imports, boilerplate ou detalhes que não sejam relevantes.

Campos obrigatórios:
- funcao
- responsabilidades
- dependencias
- relacoes
- observacoes
- arquivos_para_revisar

Campos adicionais permitidos somente quando forem sustentados pelo código real.

Retorne SOMENTE JSON válido.

Formato:
""" + SCHEMA_ANALISE


def limpar_json(texto: str) -> str:
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s*```$", "", texto)
    inicio = texto.find("{")
    fim = texto.rfind("}")

    if inicio >= 0 and fim > inicio:
        texto = texto[inicio:fim + 1]

    return texto.strip()


def formato_valido(texto: str) -> bool:
    try:
        dados = json.loads(limpar_json(texto))
    except json.JSONDecodeError:
        return False

    if not isinstance(dados, dict):
        return False

    if not CAMPOS_ANALISE.issubset(dados):
        return False

    if not isinstance(dados["funcao"], str):
        return False

    return all(
        isinstance(dados[campo], list)
        for campo in CAMPOS_ANALISE - {"funcao"}
    )


def analise_completa(analise: dict) -> bool:
    return (
        isinstance(analise, dict)
        and CAMPOS_ANALISE.issubset(analise)
    )


def preservar_conhecimentos(nome_repo: str, caminho_relativo: str, analise: dict) -> dict:
    existente = carregar_analise(nome_repo, caminho_relativo)

    if existente and isinstance(existente.get("conhecimentos"), list):
        analise["conhecimentos"] = existente["conhecimentos"]
    else:
        analise.setdefault("conhecimentos", [])

    return analise


def calcular_custo(usage) -> tuple[int, float]:
    prompt_tokens = getattr(usage, "prompt_tokens", 0)
    completion_tokens = getattr(usage, "completion_tokens", 0)
    detalhes = getattr(usage, "prompt_tokens_details", None)
    cached_tokens = getattr(detalhes, "cached_tokens", 0) or 0
    preco = PRECOS.get(MODEL)

    if not preco:
        return cached_tokens, 0.0

    tokens_normais = max(prompt_tokens - cached_tokens, 0)
    custo_entrada = tokens_normais / 1_000_000 * preco["entrada"]
    custo_cache = cached_tokens / 1_000_000 * preco["entrada_cache"]
    custo_saida = completion_tokens / 1_000_000 * preco["saida"]

    return cached_tokens, custo_entrada + custo_cache + custo_saida


def registrar_uso(response, inicio: float) -> None:
    cached_tokens, custo = calcular_custo(response.usage)

    registrar_modelo(
        MODEL,
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
        response.usage.total_tokens,
        cached_tokens,
        time.perf_counter() - inicio,
        custo
    )


def tamanho_arquivo(caminho: Path) -> int:
    return caminho.stat().st_size


def limite_batch(tamanho_bytes: int) -> int:
    tamanho_kb = tamanho_bytes / 1024

    if tamanho_kb <= BATCH_ATE_KB:
        return BATCH_MAX_ARQUIVOS_PEQUENOS

    if tamanho_kb <= BATCH_ATE_10_KB:
        return BATCH_MAX_ARQUIVOS_MEDIOS

    if tamanho_kb <= BATCH_ATE_30_KB:
        return BATCH_MAX_ARQUIVOS_GRANDES

    return 1


def reasoning_arquivo(caminho: Path) -> str:
    tamanho_kb = tamanho_arquivo(caminho) / 1024
    nome = caminho.name.lower()

    if caminho.suffix.lower() in {".xml", ".json", ".properties", ".yml", ".yaml"}:
        return "low"

    if any(nome.endswith(sufixo) for sufixo in ("dto.java", "exception.java")):
        return "low"

    if "controller" in nome or "client" in nome:
        return "low"

    if "service" in nome or "repository" in nome or "impl" in nome:
        return "low"

    if tamanho_kb > BATCH_ATE_30_KB:
        return "medium"

    if tamanho_kb > BATCH_ATE_10_KB:
        return "low"

    return "low"


def reasoning_lote(arquivos: list[tuple[str, Path]]) -> str:
    niveis = {"none": 0, "low": 1, "medium": 2, "high": 3}

    return max(
        (reasoning_arquivo(caminho) for _, caminho in arquivos),
        key=lambda nivel: niveis[nivel]
    )


def corrigir_analise(nome_repo: str, caminho_relativo: str, codigo: str, analise_bruta: str) -> dict:
    inicio = time.perf_counter()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": PROMPT_CORRECAO},
            {
                "role": "user",
                "content": (
                    f"REPOSITÓRIO: {nome_repo}\n"
                    f"ARQUIVO: {caminho_relativo}\n\n"
                    f"CÓDIGO:\n{codigo}\n\n"
                    f"ANÁLISE ORIGINAL:\n{analise_bruta}"
                )
            }
        ],
        temperature=0,
        reasoning_effort="low",
        response_format={"type": "json_object"},
        max_completion_tokens=CORRECAO_MAX_COMPLETION_TOKENS
    )

    registrar_uso(response, inicio)

    conteudo = response.choices[0].message.content or ""

    if not formato_valido(conteudo):
        raise ValueError("O modelo retornou formato inválido após a correção.")

    return json.loads(limpar_json(conteudo))


def analisar_arquivo(nome_repo: str, caminho_relativo: str) -> dict:
    registrar_analise(nome_repo, caminho_relativo)

    repo = buscar_repositorio(nome_repo)
    caminho = resolver_arquivo(repo, caminho_relativo)
    codigo = ler_arquivo(caminho)

    inicio = time.perf_counter()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": PROMPT_ANALISE},
            {
                "role": "user",
                "content": (
                    f"REPOSITÓRIO: {nome_repo}\n"
                    f"ARQUIVO: {caminho_relativo}\n\n"
                    f"CÓDIGO:\n{codigo}"
                )
            }
        ],
        temperature=0,
        reasoning_effort=reasoning_arquivo(caminho),
        response_format={"type": "json_object"},
        max_completion_tokens=ANALISE_MAX_COMPLETION_TOKENS
    )

    registrar_uso(response, inicio)

    analise_bruta = response.choices[0].message.content or ""

    if formato_valido(analise_bruta):
        analise = json.loads(limpar_json(analise_bruta))
    else:
        analise = corrigir_analise(
            nome_repo,
            caminho_relativo,
            codigo,
            analise_bruta
        )

    analise["arquivo"] = caminho_relativo
    preservar_conhecimentos(nome_repo, caminho_relativo, analise)

    salvar_analise(nome_repo, caminho_relativo, analise)

    return analise


def analisar_arquivos_lote(nome_repo: str, arquivos: list[tuple[str, Path]]) -> dict:
    if len(arquivos) == 1:
        relativo = arquivos[0][0]
        return {relativo: analisar_arquivo(nome_repo, relativo)}

    conteudo = []

    for relativo, caminho in arquivos:
        registrar_analise(nome_repo, relativo)
        codigo = ler_arquivo(caminho)
        conteudo.append(
            f"===== ARQUIVO: {relativo} =====\n"
            f"{codigo}\n"
            f"===== FIM: {relativo} ====="
        )

    inicio = time.perf_counter()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": PROMPT_ANALISE},
            {
                "role": "user",
                "content": (
                    f"REPOSITÓRIO: {nome_repo}\n\n"
                    + "\n\n".join(conteudo)
                )
            }
        ],
        temperature=0,
        reasoning_effort=reasoning_lote(arquivos),
        response_format={"type": "json_object"},
        max_completion_tokens=BATCH_MAX_COMPLETION_TOKENS
    )

    registrar_uso(response, inicio)

    bruto = response.choices[0].message.content or ""

    try:
        dados = json.loads(limpar_json(bruto))
    except json.JSONDecodeError as erro:
        logger.error(
            f"[batch] JSON inválido para {len(arquivos)} arquivos: {erro}"
        )

        meio = len(arquivos) // 2
        logger.warning(
            f"[batch] reduzindo lote: {len(arquivos)} -> "
            f"{meio} + {len(arquivos) - meio}"
        )

        analises = {}
        analises.update(analisar_arquivos_lote(nome_repo, arquivos[:meio]))
        analises.update(analisar_arquivos_lote(nome_repo, arquivos[meio:]))

        return analises

    resultados = dados.get("arquivos")

    if not isinstance(resultados, dict):
        logger.error(
            f"[batch] campo 'arquivos' inválido para {len(arquivos)} arquivos"
        )

        meio = len(arquivos) // 2
        logger.warning(
            f"[batch] reduzindo lote: {len(arquivos)} -> "
            f"{meio} + {len(arquivos) - meio}"
        )

        analises = {}
        analises.update(analisar_arquivos_lote(nome_repo, arquivos[:meio]))
        analises.update(analisar_arquivos_lote(nome_repo, arquivos[meio:]))

        return analises

    analises = {}

    for relativo, _ in arquivos:
        analise = resultados.get(relativo)

        if not isinstance(analise, dict) or not formato_valido(
            json.dumps(analise, ensure_ascii=False)
        ):
            logger.warning(f"[batch] análise inválida para {relativo}")

            meio = len(arquivos) // 2
            analises = {}
            analises.update(analisar_arquivos_lote(nome_repo, arquivos[:meio]))
            analises.update(analisar_arquivos_lote(nome_repo, arquivos[meio:]))

            return analises

        analise["arquivo"] = relativo
        preservar_conhecimentos(nome_repo, relativo, analise)
        salvar_analise(nome_repo, relativo, analise)
        analises[relativo] = analise

    return analises


def atualizar_index(nome_repo: str) -> None:
    repo = buscar_repositorio(nome_repo)
    analises = carregar_analises(nome_repo)

    index = {
        "repositorio": nome_repo,
        "path": repo["path"],
        "arquivos": [
            {
                "arquivo": analise.get("arquivo"),
                "path": analise.get("path"),
                "funcao": analise.get("funcao")
            }
            for analise in analises
        ]
    }

    salvar_index(nome_repo, index)


def criar_lotes(fila: list[Path], repo_path: str) -> list[list[tuple[str, Path]]]:
    lotes = []
    fila_restante = list(fila)

    while fila_restante:
        primeiro = fila_restante.pop(0)
        relativo = str(
            primeiro.relative_to(Path(repo_path))
        ).replace("\\", "/")

        tamanho_primeiro = tamanho_arquivo(primeiro)
        limite = limite_batch(tamanho_primeiro)
        lote = [(relativo, primeiro)]
        tamanho_total = tamanho_primeiro

        if limite > 1:
            candidatos = []

            for arquivo in fila_restante:
                tamanho = tamanho_arquivo(arquivo)

                if limite_batch(tamanho) != limite:
                    continue

                if tamanho_total + tamanho > BATCH_MAX_KB * 1024:
                    continue

                candidatos.append(arquivo)
                tamanho_total += tamanho

                if len(lote) + len(candidatos) >= limite:
                    break

            for arquivo in candidatos:
                fila_restante.remove(arquivo)

                relativo_candidato = str(
                    arquivo.relative_to(Path(repo_path))
                ).replace("\\", "/")

                lote.append((relativo_candidato, arquivo))

        lotes.append(lote)

    return lotes


def analisar_repositorio(nome_repo: str, forcar: bool = False) -> dict:
    repo = buscar_repositorio(nome_repo)
    arquivos = listar_arquivos(repo)

    caminhos = {
        str(arquivo.relative_to(Path(repo["path"]))).replace("\\", "/"): arquivo
        for arquivo in arquivos
    }

    existentes = {
        analise.get("arquivo")
        for analise in carregar_analises(nome_repo)
        if analise_completa(analise)
    }

    if forcar:
        fila = list(arquivos)
    else:
        fila = [
            arquivo
            for relativo, arquivo in caminhos.items()
            if relativo not in existentes
        ]

    fila = list(dict.fromkeys(fila))
    revisoes = {}
    analisados_agora = 0
    processados = 0

    while fila:
        lotes = criar_lotes(fila, repo["path"])

        for lote in lotes:
            for _, caminho in lote:
                if caminho in fila:
                    fila.remove(caminho)

            processados += len(lote)
            nomes = [relativo for relativo, _ in lote]

            logger.info(
                f"ANÁLSIE | {processados} arquivos processados "
                f"| fila: {len(fila)} "
                f"| lote: {len(lote)} "
                f"| {', '.join(nomes)}"
            )

            if len(lote) == 1:
                relativo = lote[0][0]
                analises = {
                    relativo: analisar_arquivo(nome_repo, relativo)
                }
            else:
                try:
                    analises = analisar_arquivos_lote(nome_repo, lote)
                except ValueError as erro:
                    logger.error(f"[batch] falhou: {erro}")
                    logger.warning(
                        f"[batch] fallback individual: {len(lote)} arquivos"
                    )

                    analises = {}

                    for relativo, _ in lote:
                        analises[relativo] = analisar_arquivo(
                            nome_repo,
                            relativo
                        )

            analisados_agora += len(analises)

            for relativo, analise in analises.items():
                if not isinstance(analise, dict):
                    logger.error(
                        f"[ANÁLISE] resultado inválido | "
                        f"arquivo={relativo} | "
                        f"tipo={type(analise).__name__} | "
                        f"conteúdo={analise}"
                    )
                    continue

                for item in analise.get("arquivos_para_revisar", []):
                    if not isinstance(item, dict):
                        continue

                    repo_revisar = item.get("repositorio")
                    arquivo_revisar = item.get("arquivo")

                    if repo_revisar != nome_repo:
                        continue

                    if arquivo_revisar not in caminhos:
                        continue

                    quantidade = revisoes.get(arquivo_revisar, 0)

                    if quantidade >= 1:
                        continue

                    revisoes[arquivo_revisar] = quantidade + 1
                    arquivo_path = caminhos[arquivo_revisar]

                    if arquivo_path in fila:
                        continue

                    fila.append(arquivo_path)

                    logger.info(
                        f"[revisão] {repo_revisar} -> {arquivo_revisar}"
                    )

    atualizar_index(nome_repo)

    return {
        "repositorio": nome_repo,
        "arquivos_analisados_agora": analisados_agora,
        "arquivos_com_conhecimento": len(carregar_analises(nome_repo))
    }

def atualizar_conhecimento_arquivo(nome_repo: str, caminho_relativo: str, conhecimento: str) -> None:
    """Registra o log e repassa a atualização para o storage."""
    registrar_conhecimento(nome_repo, caminho_relativo)
    adicionar_conhecimento(nome_repo, caminho_relativo, conhecimento)