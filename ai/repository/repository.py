import json
from pathlib import Path


EXTENSOES_CODIGO = {
    ".py",
    ".java",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".cs",
    ".go",
    ".rs",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".php",
    ".rb",
    ".kt",
    ".kts",
    ".scala",
    ".sql",
}

ARQUIVOS_IMPORTANTES = {
    "pom.xml",
    "package.json",
    "docker-compose.yml",
    "docker-compose.yaml",
    "application.properties",
    "application.yml",
    "application.yaml",
}

IGNORAR = {
    ".git",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "target",
    "build",
    "dist",
}


BASE_DIR = Path(__file__).resolve().parents[2]
ARQUIVO_REPOSITORIOS = (
    BASE_DIR / "repos" / "repositorios.json"
)


def carregar_repositorios() -> list[dict]:
    with open(
        ARQUIVO_REPOSITORIOS,
        encoding="utf-8"
    ) as arquivo:
        return json.load(arquivo)["repositorios"]


def buscar_repositorio(nome: str) -> dict:
    for repo in carregar_repositorios():
        if repo["nome"].casefold() == nome.casefold():
            return repo

    raise ValueError(
        f"Repositório não encontrado: {nome}"
    )


def listar_arquivos(repo: dict) -> list[Path]:
    raiz = Path(repo["path"])

    if not raiz.exists():
        raise FileNotFoundError(
            f"Repositório não encontrado: {raiz}"
        )

    arquivos = []

    for caminho in raiz.rglob("*"):

        if not caminho.is_file():
            continue

        if any(
            parte in IGNORAR
            for parte in caminho.parts
        ):
            continue

        extensao = caminho.suffix.lower()

        if (
            extensao not in EXTENSOES_CODIGO
            and caminho.name not in ARQUIVOS_IMPORTANTES
        ):
            continue

        arquivos.append(caminho)

    return sorted(arquivos)


def resolver_arquivo(
    repo: dict,
    arquivo: str
) -> Path:

    raiz = Path(repo["path"]).resolve()

    caminho = (
        raiz / arquivo
    ).resolve()

    if raiz not in caminho.parents and caminho != raiz:
        raise ValueError(
            "Arquivo fora do repositório."
        )

    if not caminho.exists() or not caminho.is_file():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {arquivo}"
        )

    return caminho


def ler_arquivo(caminho: Path) -> str:

    try:
        return caminho.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:

        return caminho.read_text(
            encoding="latin-1"
        )