import json
import re

from ai.repository.repository import (
    carregar_repositorios,
    buscar_repositorio,
    listar_arquivos,
    resolver_arquivo,
    ler_arquivo
)

from ai.analyzer.analyzer import analisar_arquivo, analisar_repositorio, atualizar_conhecimento_arquivo
from ai.analyzer.storage import carregar_analise
from ai.report.report import gerar_relatorio


def listar_repositorios() -> str:
    """Lista todos os repositórios disponíveis para análise."""
    return json.dumps(carregar_repositorios(), ensure_ascii=False)


def listar_arquivos_repo(repositorio: str, filtro: str | None = None) -> str:
    """Lista os arquivos de um repositório, opcionalmente filtrando pelo caminho ou nome."""
    repo = buscar_repositorio(repositorio)
    arquivos = listar_arquivos(repo)
    resultado = []

    for arquivo in arquivos:
        relativo = str(arquivo.relative_to(repo["path"])).replace("\\", "/")

        if filtro and filtro.casefold() not in relativo.casefold():
            continue

        resultado.append(relativo)

    return json.dumps(resultado, ensure_ascii=False)


def consultar_analises(repositorio: str, arquivos: list[str]) -> str:
    """Consulta as análises armazenadas de vários arquivos."""
    resultado = {}

    for arquivo in arquivos:
        analise = carregar_analise(repositorio, arquivo)
        resultado[arquivo] = analise

    return json.dumps(resultado, ensure_ascii=False)


def ler_codigo(repositorio: str, arquivo: str, objetivo: str | None = None) -> str:
    """Lê o código real e atual de um arquivo do repositório."""
    repo = buscar_repositorio(repositorio)
    caminho = resolver_arquivo(repo, arquivo)
    codigo = ler_arquivo(caminho)

    return (
        f"REPOSITÓRIO: {repositorio}\n"
        f"ARQUIVO: {arquivo}\n"
        f"OBJETIVO: {objetivo or 'Não especificado'}\n\n"
        f"{codigo}"
    )


def buscar_codigo(
    repositorio: str,
    termo: str,
    diretorio: str | None = None,
    contexto: int = 5
) -> str:
    """Busca um termo no código real e retorna as ocorrências com contexto."""
    repo = buscar_repositorio(repositorio)
    arquivos = listar_arquivos(repo)

    if diretorio:
        diretorio_normalizado = diretorio.replace("\\", "/").strip("/").casefold()
        arquivos_filtrados = []

        for arquivo in arquivos:
            relativo = (
                str(arquivo.relative_to(repo["path"]))
                .replace("\\", "/")
                .strip("/")
                .casefold()
            )

            if f"/{diretorio_normalizado}/" in f"/{relativo}/":
                arquivos_filtrados.append(arquivo)

        arquivos = arquivos_filtrados

    resultados = []
    termo_normalizado = termo.casefold()

    for caminho in arquivos:
        relativo = str(caminho.relative_to(repo["path"])).replace("\\", "/")

        try:
            linhas = ler_arquivo(caminho).splitlines()
        except Exception:
            continue

        for numero, linha in enumerate(linhas, start=1):
            if termo_normalizado not in linha.casefold():
                continue

            inicio = max(0, numero - 1 - contexto)
            fim = min(len(linhas), numero + contexto)

            trecho = "\n".join(
                f"{i + 1}: {linhas[i]}"
                for i in range(inicio, fim)
            )

            resultados.append({
                "arquivo": relativo,
                "linha": numero,
                "trecho": trecho
            })

    return json.dumps(resultados, ensure_ascii=False)


def _normalizar_relativo(repo: dict, caminho) -> str:
    return str(caminho.relative_to(repo["path"])).replace("\\", "/")


def _arquivo_elegivel(caminho) -> bool:
    return caminho.suffix.lower() in {
        ".java",
        ".kt",
        ".kts",
        ".groovy",
        ".scala",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".py",
        ".cs",
        ".cpp",
        ".c",
        ".h",
        ".hpp"
    }


def _linhas_arquivo(caminho) -> list[str]:
    return ler_arquivo(caminho).splitlines()


def _remover_anotacoes_java(texto: str) -> str:
    return re.sub(
        r"@\w+(?:\([^)]*\))?\s*",
        "",
        texto
    )


def _dividir_argumentos(texto: str) -> list[str]:
    partes = []
    atual = []
    profundidade_parenteses = 0
    profundidade_generics = 0
    dentro_string = False
    escape = False
    quote = None

    for char in texto:
        if dentro_string:
            atual.append(char)

            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                dentro_string = False

            continue

        if char in {"'", '"'}:
            dentro_string = True
            quote = char
            atual.append(char)
            continue

        if char == "(":
            profundidade_parenteses += 1
        elif char == ")" and profundidade_parenteses > 0:
            profundidade_parenteses -= 1
        elif char == "<":
            profundidade_generics += 1
        elif char == ">" and profundidade_generics > 0:
            profundidade_generics -= 1

        if (
            char == ","
            and profundidade_parenteses == 0
            and profundidade_generics == 0
        ):
            partes.append("".join(atual).strip())
            atual = []
            continue

        atual.append(char)

    if atual:
        partes.append("".join(atual).strip())

    return partes


def _parsear_parametros(parametros: str) -> list[dict]:
    resultado = []

    for indice, parametro in enumerate(_dividir_argumentos(parametros)):
        parametro = _remover_anotacoes_java(parametro)
        parametro = re.sub(r"\bfinal\b\s+", "", parametro).strip()

        match = re.search(
            r"(?P<tipo>.+?)\s+(?P<nome>[A-Za-z_$][\w$]*)$",
            parametro
        )

        if not match:
            continue

        resultado.append({
            "indice": indice,
            "tipo": match.group("tipo").strip(),
            "nome": match.group("nome")
        })

    return resultado


def _encontrar_declaracoes_simbolo(
    linhas: list[str],
    simbolo: str
) -> list[dict]:
    resultados = []

    padrao_declaracao = re.compile(
        rf"^\s*"
        rf"(?:(?:public|private|protected|static|final|volatile|transient|"
        rf"synchronized|abstract|native|strictfp)\s+)*"
        rf"(?:[\w$]+\s*(?:<[^;\n{{}}()]+>)?(?:\[\])*(?:\s*\.\s*)?)+"
        rf"\s+{re.escape(simbolo)}"
        rf"\s*=\s*(?P<valor>.+?)\s*;\s*$"
    )

    padrao_declaracao_sem_valor = re.compile(
        rf"^\s*"
        rf"(?:(?:public|private|protected|static|final|volatile|transient|"
        rf"synchronized|abstract|native|strictfp)\s+)*"
        rf"(?:[\w$]+\s*(?:<[^;\n{{}}()]+>)?(?:\[\])*(?:\s*\.\s*)?)+"
        rf"\s+{re.escape(simbolo)}"
        rf"\s*;\s*$"
    )

    padrao_atribuicao = re.compile(
        rf"^\s*(?:this\.)?{re.escape(simbolo)}"
        rf"\s*=\s*(?P<valor>.+?)\s*;\s*$"
    )

    for numero, linha in enumerate(linhas, start=1):
        match = padrao_declaracao.match(linha)

        if match:
            resultados.append({
                "tipo": "variavel",
                "linha": numero,
                "expressao": match.group("valor")
            })
            continue

        match = padrao_declaracao_sem_valor.match(linha)

        if match:
            resultados.append({
                "tipo": "variavel",
                "linha": numero,
                "expressao": None
            })
            continue

        match = padrao_atribuicao.match(linha)

        if match:
            resultados.append({
                "tipo": "atribuicao",
                "linha": numero,
                "expressao": match.group("valor")
            })

    texto = "\n".join(linhas)

    padrao_metodo = re.compile(
        r"(?:"
        r"(?:(?:public|private|protected|static|final|synchronized|abstract|native)\s+)*"
        r"(?:[\w$]+\s*(?:<[^>{}()]+>)?(?:\[\])*(?:\s*\.\s*)?)+"
        r"\s+"
        r"(?P<nome>[A-Za-z_$][\w$]*)"
        r"\s*\("
        r"(?P<params>[^()]*)"
        r"\)"
    )

    for match in padrao_metodo.finditer(texto):
        parametros = _parsear_parametros(match.group("params"))

        for parametro in parametros:
            if parametro["nome"] != simbolo:
                continue

            linha = texto[:match.start()].count("\n") + 1

            resultados.append({
                "tipo": "parametro",
                "linha": linha,
                "metodo": match.group("nome"),
                "indice": parametro["indice"],
                "tipo_dado": parametro["tipo"],
                "expressao": None
            })

    return resultados


def _extrair_argumentos_chamada(
    texto: str,
    nome_metodo: str
) -> list[dict]:
    resultados = []

    padrao = re.compile(
        rf"(?<![\w$]){re.escape(nome_metodo)}\s*\("
    )

    for match in padrao.finditer(texto):
        inicio = match.end()
        profundidade = 1
        i = inicio
        atual = []
        argumentos = []

        dentro_string = False
        quote = None
        escape = False

        while i < len(texto) and profundidade > 0:
            char = texto[i]

            if dentro_string:
                atual.append(char)

                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == quote:
                    dentro_string = False

                i += 1
                continue

            if char in {"'", '"'}:
                dentro_string = True
                quote = char
                atual.append(char)

            elif char == "(":
                profundidade += 1
                atual.append(char)

            elif char == ")":
                profundidade -= 1

                if profundidade == 0:
                    argumento = "".join(atual).strip()

                    if argumento:
                        argumentos.append(argumento)

                    break

                atual.append(char)

            elif char == "," and profundidade == 1:
                argumentos.append("".join(atual).strip())
                atual = []

            else:
                atual.append(char)

            i += 1

        linha = texto[:match.start()].count("\n") + 1

        resultados.append({
            "linha": linha,
            "argumentos": argumentos,
            "expressao": texto[match.start():i + 1]
        })

    return resultados


def _resolver_expressao_simples(
    repositorio: str,
    arquivo: str,
    expressao: str,
    pilha: list[str]
) -> dict:
    expressao = expressao.strip()

    match = re.fullmatch(
        r'"((?:\\.|[^"\\])*)"',
        expressao,
        re.DOTALL
    )

    if match:
        return {
            "resolvido": True,
            "valor": match.group(1),
            "origem": "literal"
        }

    match = re.fullmatch(
        r"'((?:\\.|[^'\\])*)'",
        expressao,
        re.DOTALL
    )

    if match:
        return {
            "resolvido": True,
            "valor": match.group(1),
            "origem": "literal"
        }

    if re.fullmatch(
        r"-?\d+(?:\.\d+)?",
        expressao
    ):
        return {
            "resolvido": True,
            "valor": expressao,
            "origem": "literal"
        }

    if expressao in {"true", "false", "null"}:
        return {
            "resolvido": True,
            "valor": expressao,
            "origem": "literal"
        }

    identificador = re.fullmatch(
        r"(?:this\.)?([A-Za-z_$][\w$]*)",
        expressao
    )

    if identificador:
        outro_simbolo = identificador.group(1)

        if outro_simbolo in pilha:
            return {
                "resolvido": False,
                "valor": None,
                "motivo": "Referência circular detectada.",
                "cadeia": pilha + [outro_simbolo]
            }

        return _resolver_referencia_interno(
            repositorio,
            arquivo,
            outro_simbolo,
            None,
            pilha + [outro_simbolo]
        )

    return {
        "resolvido": False,
        "valor": None,
        "expressao": expressao,
        "motivo": "Expressão não determinada pelo resolvedor."
    }


def _resolver_referencia_interno(
    repositorio: str,
    arquivo: str,
    simbolo: str,
    linha: int | None,
    pilha: list[str] | None = None
) -> dict:
    pilha = pilha or [simbolo]

    repo = buscar_repositorio(repositorio)
    caminho = resolver_arquivo(repo, arquivo)

    try:
        linhas = _linhas_arquivo(caminho)
    except Exception as erro:
        return {
            "simbolo": simbolo,
            "resolvido": False,
            "motivo": f"Não foi possível ler o arquivo: {erro}"
        }

    declaracoes = _encontrar_declaracoes_simbolo(
        linhas,
        simbolo
    )

    if linha is not None:
        declaracoes = sorted(
            declaracoes,
            key=lambda item: (
                0 if item["linha"] <= linha else 1,
                abs(item["linha"] - linha)
            )
        )

    declaracoes_com_valor = [
        item
        for item in declaracoes
        if item.get("expressao")
    ]

    if declaracoes_com_valor:

        resolucoes = []

        for declaracao in declaracoes_com_valor:
            resultado = _resolver_expressao_simples(
                repositorio,
                arquivo,
                declaracao["expressao"],
                pilha
            )

            resolucoes.append({
                "declaracao": declaracao,
                "resultado": resultado
            })

        valores = [
            item["resultado"].get("valor")
            for item in resolucoes
            if item["resultado"].get("resolvido")
        ]

        valores = list(dict.fromkeys(valores))

        if len(valores) == 1:
            return {
                "simbolo": simbolo,
                "resolvido": True,
                "valor": valores[0],
                "declaracoes": declaracoes,
                "cadeia": [
                    {
                        "arquivo": arquivo,
                        "linha": item["declaracao"]["linha"],
                        "expressao": item["declaracao"].get("expressao")
                    }
                    for item in resolucoes
                ]
            }

        if len(valores) > 1:
            return {
                "simbolo": simbolo,
                "resolvido": False,
                "motivo": "Há múltiplos valores possíveis.",
                "possibilidades": valores,
                "declaracoes": declaracoes
            }

    parametros = [
        item
        for item in declaracoes
        if item.get("tipo") == "parametro"
    ]

    if parametros:

        resultados_chamadas = []

        for parametro in parametros:
            metodo = parametro["metodo"]
            indice = parametro["indice"]

            for outro_caminho in listar_arquivos(repo):

                if not _arquivo_elegivel(outro_caminho):
                    continue

                try:
                    texto = ler_arquivo(outro_caminho)
                except Exception:
                    continue

                chamadas = _extrair_argumentos_chamada(
                    texto,
                    metodo
                )

                for chamada in chamadas:
                    argumentos = chamada["argumentos"]

                    if indice >= len(argumentos):
                        continue

                    expressao = argumentos[indice].strip()

                    if not expressao:
                        continue

                    arquivo_chamada = _normalizar_relativo(
                        repo,
                        outro_caminho
                    )

                    if re.fullmatch(
                        r"(?:this\.)?[A-Za-z_$][\w$]*",
                        expressao
                    ):
                        argumento_simbolo = expressao.replace(
                            "this.",
                            "",
                            1
                        )

                        if argumento_simbolo in pilha:
                            continue

                        resultado = _resolver_referencia_interno(
                            repositorio,
                            arquivo_chamada,
                            argumento_simbolo,
                            chamada["linha"],
                            pilha + [argumento_simbolo]
                        )
                    else:
                        resultado = _resolver_expressao_simples(
                            repositorio,
                            arquivo_chamada,
                            expressao,
                            pilha
                        )

                    resultados_chamadas.append({
                        "metodo": metodo,
                        "parametro": simbolo,
                        "indice": indice,
                        "arquivo_chamada": arquivo_chamada,
                        "linha_chamada": chamada["linha"],
                        "argumento": expressao,
                        "resultado": resultado
                    })

        valores = [
            item["resultado"].get("valor")
            for item in resultados_chamadas
            if item["resultado"].get("resolvido")
        ]

        valores = list(dict.fromkeys(valores))

        if len(valores) == 1:
            return {
                "simbolo": simbolo,
                "resolvido": True,
                "valor": valores[0],
                "declaracoes": parametros,
                "chamadas": resultados_chamadas
            }

        if len(valores) > 1:
            return {
                "simbolo": simbolo,
                "resolvido": False,
                "motivo": (
                    "O parâmetro recebe valores diferentes "
                    "em chamadas distintas."
                ),
                "possibilidades": valores,
                "declaracoes": parametros,
                "chamadas": resultados_chamadas
            }

        return {
            "simbolo": simbolo,
            "resolvido": False,
            "motivo": (
                "O parâmetro foi encontrado, mas seus valores "
                "não puderam ser determinados."
            ),
            "declaracoes": parametros,
            "chamadas": resultados_chamadas
        }

    outras_declaracoes = []

    for outro_caminho in listar_arquivos(repo):
        if outro_caminho == caminho:
            continue

        if not _arquivo_elegivel(outro_caminho):
            continue

        try:
            outras_linhas = _linhas_arquivo(outro_caminho)
        except Exception:
            continue

        encontradas = _encontrar_declaracoes_simbolo(
            outras_linhas,
            simbolo
        )

        for declaracao in encontradas:
            declaracao = dict(declaracao)
            declaracao["arquivo"] = _normalizar_relativo(
                repo,
                outro_caminho
            )
            outras_declaracoes.append(declaracao)

    declaracoes_com_valor = [
        item
        for item in outras_declaracoes
        if item.get("expressao")
    ]

    if len(declaracoes_com_valor) == 1:
        declaracao = declaracoes_com_valor[0]

        resultado = _resolver_expressao_simples(
            repositorio,
            declaracao["arquivo"],
            declaracao["expressao"],
            pilha
        )

        if resultado.get("resolvido"):
            return {
                "simbolo": simbolo,
                "resolvido": True,
                "valor": resultado["valor"],
                "declaracoes": [declaracao]
            }

    if len(declaracoes_com_valor) > 1:
        valores = []

        for declaracao in declaracoes_com_valor:
            resultado = _resolver_expressao_simples(
                repositorio,
                declaracao["arquivo"],
                declaracao["expressao"],
                pilha
            )

            if resultado.get("resolvido"):
                valores.append(resultado["valor"])

        valores = list(dict.fromkeys(valores))

        if len(valores) == 1:
            return {
                "simbolo": simbolo,
                "resolvido": True,
                "valor": valores[0],
                "declaracoes": declaracoes_com_valor
            }

        if valores:
            return {
                "simbolo": simbolo,
                "resolvido": False,
                "motivo": "Há múltiplas definições com valores diferentes.",
                "possibilidades": valores,
                "declaracoes": declaracoes_com_valor
            }

    return {
        "simbolo": simbolo,
        "resolvido": False,
        "motivo": (
            "Declaração ou valor da referência não pôde ser determinado "
            "com segurança."
        ),
        "declaracoes": declaracoes,
        "outras_declaracoes": outras_declaracoes
    }


def resolver_referencia(
    repositorio: str,
    arquivo: str,
    simbolo: str,
    linha: int | None = None
) -> str:
    """Resolve uma referência no código real até seu valor conhecido."""
    resultado = _resolver_referencia_interno(
        repositorio,
        arquivo,
        simbolo,
        linha
    )

    return json.dumps(
        resultado,
        ensure_ascii=False,
        indent=2
    )


def encontrar_referencias(
    repositorio: str,
    simbolo: str,
    diretorio: str | None = None,
    arquivo: str | None = None
) -> str:
    """Encontra usos de um símbolo no código real."""
    repo = buscar_repositorio(repositorio)
    arquivos = listar_arquivos(repo)

    if arquivo:
        arquivo_normalizado = (
            arquivo.replace("\\", "/")
            .strip("/")
            .casefold()
        )

        arquivos = [
            caminho
            for caminho in arquivos
            if _normalizar_relativo(
                repo,
                caminho
            ).casefold() == arquivo_normalizado
        ]

    if diretorio:
        diretorio_normalizado = (
            diretorio.replace("\\", "/")
            .strip("/")
            .casefold()
        )

        arquivos = [
            caminho
            for caminho in arquivos
            if f"/{diretorio_normalizado}/" in
            f"/{_normalizar_relativo(repo, caminho).strip('/').casefold()}/"
        ]

    padrao = re.compile(
        rf"(?<![\w$]){re.escape(simbolo)}(?![\w$])"
    )

    resultados = []

    for caminho in arquivos:
        if not _arquivo_elegivel(caminho):
            continue

        try:
            linhas = _linhas_arquivo(caminho)
        except Exception:
            continue

        relativo = _normalizar_relativo(
            repo,
            caminho
        )

        for numero, linha in enumerate(linhas, start=1):
            for match in padrao.finditer(linha):
                resultados.append({
                    "arquivo": relativo,
                    "linha": numero,
                    "coluna": match.start() + 1,
                    "ocorrencia": linha.strip()
                })

    return json.dumps(
        resultados,
        ensure_ascii=False
    )


def atualizar_conhecimento(
    repositorio: str,
    arquivo: str,
    conhecimento: str
) -> str:
    """Adiciona conhecimento confirmado ao conhecimento armazenado do arquivo."""
    atualizar_conhecimento_arquivo(repositorio, arquivo, conhecimento)

    return f"Conhecimento atualizado para {repositorio}/{arquivo}."

def analisar_arquivo_tool(repositorio: str, arquivo: str) -> str:
    """Analisa ou reanalisa um arquivo usando seu código real e o contexto atual."""
    analise = analisar_arquivo(repositorio, arquivo)
    return json.dumps(analise, ensure_ascii=False)


def analisar_repositorio_tool(repositorio: str, forcar: bool = False) -> str:
    """Analisa um repositório inteiro. Use forcar=true para analisar tudo novamente."""
    resultado = analisar_repositorio(repositorio, forcar)
    return json.dumps(resultado, ensure_ascii=False)


def gerar_relatorio_tool(repositorio: str | None = None) -> str:
    """Gera um relatório JSON com o conhecimento armazenado."""
    caminho = gerar_relatorio(repositorio)
    return f"Relatório gerado em: {caminho}"


TOOLS = {
    "listar_repositorios": listar_repositorios,
    "listar_arquivos_repo": listar_arquivos_repo,
    "consultar_analises": consultar_analises,
    "buscar_codigo": buscar_codigo,
    "encontrar_referencias": encontrar_referencias,
    "resolver_referencia": resolver_referencia,
    "ler_codigo": ler_codigo,
    "atualizar_conhecimento": atualizar_conhecimento,
    "analisar_arquivo": analisar_arquivo_tool,
    "analisar_repositorio": analisar_repositorio_tool,
    "gerar_relatorio": gerar_relatorio_tool
}


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "listar_repositorios",
            "description": (
                "Lista os repositórios disponíveis. "
                "Use quando precisar descobrir quais projetos existem."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_arquivos_repo",
            "description": (
                "Lista arquivos de um repositório. "
                "Use para localizar arquivos relevantes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repositorio": {"type": "string"},
                    "filtro": {"type": "string"}
                },
                "required": ["repositorio"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_analises",
            "description": (
                "Recupera o conhecimento técnico JÁ ARMAZENADO de vários arquivos. "
                "Use esta ferramenta PRIMEIRO quando a pergunta envolver arquivos, classes "
                "ou componentes que já possam ter sido analisados. "
                "Prefira consultar vários arquivos em uma única chamada. "
                "NÃO leia o código real antes de consultar as análises armazenadas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repositorio": {"type": "string"},
                    "arquivos": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["repositorio", "arquivos"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_codigo",
            "description": (
                "Busca um termo no código REAL de um repositório e retorna todas as "
                "ocorrências encontradas com arquivo, linha e contexto. "
                "Use para localizar métodos, classes, variáveis, strings, anotações, "
                "chamadas ou outros elementos antes de ler arquivos inteiros."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repositorio": {"type": "string"},
                    "termo": {"type": "string"},
                    "diretorio": {"type": "string"},
                    "contexto": {"type": "integer"}
                },
                "required": ["repositorio", "termo"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "encontrar_referencias",
            "description": (
                "Encontra ocorrências de um símbolo no código REAL do repositório. "
                "Use para descobrir onde uma variável, constante, campo, parâmetro, "
                "método ou outro símbolo é utilizado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repositorio": {"type": "string"},
                    "simbolo": {"type": "string"},
                    "diretorio": {"type": "string"},
                    "arquivo": {"type": "string"}
                },
                "required": ["repositorio", "simbolo"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resolver_referencia",
            "description": (
                "Resolve uma referência no código REAL até seu valor conhecido. "
                "Use quando uma variável, constante, campo ou parâmetro estiver "
                "representado por outro símbolo ou precisar ser rastreado até sua origem. "
                "A ferramenta tenta seguir declarações, atribuições e argumentos "
                "passados entre métodos. Nunca trate o nome de uma variável como seu valor."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repositorio": {"type": "string"},
                    "arquivo": {"type": "string"},
                    "simbolo": {"type": "string"},
                    "linha": {"type": "integer"}
                },
                "required": [
                    "repositorio",
                    "arquivo",
                    "simbolo"
                ],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ler_codigo",
            "description": (
                "Lê o código REAL e atual do arquivo. "
                "Use quando precisar confirmar uma implementação, chamada, condição, "
                "valor, regra ou qualquer detalhe que não possa ser determinado com "
                "segurança pela análise armazenada ou pela busca de código. "
                "O código real tem prioridade sobre análises armazenadas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repositorio": {"type": "string"},
                    "arquivo": {"type": "string"},
                    "objetivo": {"type": "string"}
                },
                "required": ["repositorio", "arquivo"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "atualizar_conhecimento",
            "description": (
                "Adiciona ao conhecimento armazenado de um arquivo uma informação "
                "nova e confirmada diretamente pelo código consultado. "
                "Use depois de ler e interpretar código quando houver um fato útil "
                "que ainda não esteja armazenado. "
                "Não registre hipóteses, informações genéricas ou duplicadas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repositorio": {"type": "string"},
                    "arquivo": {"type": "string"},
                    "conhecimento": {"type": "string"}
                },
                "required": [
                    "repositorio",
                    "arquivo",
                    "conhecimento"
                ],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analisar_arquivo",
            "description": (
                "Analisa ou reanalisa um arquivo usando o código REAL. "
                "Use SOMENTE quando o usuário pedir explicitamente para analisar, "
                "reanalisar ou atualizar a análise do arquivo. "
                "Para perguntas normais, consulte primeiro consultar_analises e, "
                "se necessário, use buscar_codigo e ler_codigo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repositorio": {"type": "string"},
                    "arquivo": {"type": "string"}
                },
                "required": [
                    "repositorio",
                    "arquivo"
                ],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analisar_repositorio",
            "description": (
                "Analisa tecnicamente um repositório. "
                "forcar=false: continua a análise existente e analisa somente arquivos "
                "ainda não analisados. "
                "forcar=true: descarta o progresso e refaz a análise de todos os arquivos. "
                "Use true SOMENTE quando o usuário pedir explicitamente para refazer, "
                "reanalisar ou começar novamente a análise completa."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repositorio": {"type": "string"},
                    "forcar": {"type": "boolean"}
                },
                "required": ["repositorio"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gerar_relatorio",
            "description": (
                "Gera um relatório JSON do conhecimento armazenado. "
                "Pode gerar de um repositório específico ou de todos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repositorio": {"type": "string"}
                },
                "required": [],
                "additionalProperties": False
            }
        }
    }
]