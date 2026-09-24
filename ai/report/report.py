import json
from datetime import datetime
from pathlib import Path

from ai.repository.repository import carregar_repositorios
from ai.analyzer.storage import carregar_analises


BASE_DIR = Path(__file__).resolve().parents[2]
PASTA_RELATORIOS = BASE_DIR / "relatorios"


def gerar_relatorio(
    nome_repo: str | None = None
) -> str:

    PASTA_RELATORIOS.mkdir(
        parents=True,
        exist_ok=True
    )

    repositorios = carregar_repositorios()

    selecionados = repositorios

    if nome_repo:
        selecionados = [
            repo
            for repo in repositorios
            if repo["nome"].casefold()
            == nome_repo.casefold()
        ]

        if not selecionados:
            raise ValueError(
                f"Repositório não encontrado: {nome_repo}"
            )

    dados = {
        "gerado_em": datetime.now().isoformat(),
        "repositorios": []
    }

    for repo in selecionados:
        dados["repositorios"].append(
            {
                "nome": repo["nome"],
                "path": repo["path"],
                "arquivos": carregar_analises(
                    repo["nome"]
                )
            }
        )

    nome_arquivo = (
        f"{nome_repo}.json"
        if nome_repo
        else "projeto-completo.json"
    )

    destino = PASTA_RELATORIOS / nome_arquivo

    with open(
        destino,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            dados,
            arquivo,
            ensure_ascii=False,
            indent=2
        )

    return str(destino)