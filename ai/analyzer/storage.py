import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
BASE_CONHECIMENTO = BASE_DIR / "conhecimento"
ARQUIVO_CONHECIMENTO = "repositorio.txt"


def caminho_conhecimento(nome_repo: str) -> Path:
    return diretorio_repositorio(nome_repo) / ARQUIVO_CONHECIMENTO


def salvar_conhecimento(nome_repo: str, conteudo: str) -> None:
    destino = caminho_conhecimento(nome_repo)

    with open(destino, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)


def carregar_conhecimento(nome_repo: str) -> str | None:
    caminho = caminho_conhecimento(nome_repo)

    if not caminho.exists():
        return None

    return caminho.read_text(encoding="utf-8")


def diretorio_repositorio(nome_repo: str) -> Path:
    caminho = BASE_CONHECIMENTO / nome_repo
    (caminho / "arquivos").mkdir(parents=True, exist_ok=True)
    return caminho


def id_arquivo(caminho_relativo: str) -> str:
    return caminho_relativo.replace("\\", "_").replace("/", "_")


def caminho_analise(nome_repo: str, caminho_relativo: str) -> Path:
    return (
        diretorio_repositorio(nome_repo)
        / "arquivos"
        / f"{id_arquivo(caminho_relativo)}.json"
    )


def salvar_analise(nome_repo: str, caminho_relativo: str, analise: dict) -> None:
    destino = caminho_analise(nome_repo, caminho_relativo)

    with open(destino, "w", encoding="utf-8") as arquivo:
        json.dump(analise, arquivo, ensure_ascii=False, indent=2)


def carregar_analises(nome_repo: str) -> list[dict]:
    pasta = diretorio_repositorio(nome_repo) / "arquivos"
    resultado = []

    for arquivo in pasta.glob("*.json"):
        try:
            with open(arquivo, encoding="utf-8") as f:
                resultado.append(json.load(f))
        except json.JSONDecodeError:
            continue

    return resultado


def carregar_analise(nome_repo: str, caminho_relativo: str) -> dict | None:
    caminho = caminho_analise(nome_repo, caminho_relativo)

    if not caminho.exists():
        return None

    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def salvar_index(nome_repo: str, index: dict) -> None:
    destino = diretorio_repositorio(nome_repo) / "index.json"

    with open(destino, "w", encoding="utf-8") as arquivo:
        json.dump(index, arquivo, ensure_ascii=False, indent=2)


def carregar_index(nome_repo: str) -> dict:
    destino = diretorio_repositorio(nome_repo) / "index.json"

    if not destino.exists():
        return {
            "repositorio": nome_repo,
            "arquivos": []
        }

    with open(destino, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def tem_conhecimento(nome_repo: str) -> bool:
    return len(carregar_analises(nome_repo)) > 0


def adicionar_conhecimento(
    nome_repo: str,
    caminho_relativo: str,
    conhecimento: str
) -> None:
    analise = carregar_analise(nome_repo, caminho_relativo)

    if analise is None:
        analise = {
            "arquivo": caminho_relativo,
            "conhecimentos": []
        }

    conhecimentos = analise.setdefault("conhecimentos", [])
    conhecimento = conhecimento.strip()

    if not conhecimento or conhecimento in conhecimentos:
        return

    conhecimentos.append(conhecimento)

    salvar_analise(
        nome_repo,
        caminho_relativo,
        analise
    )