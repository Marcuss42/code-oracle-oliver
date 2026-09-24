import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "oracle.log"

logger = logging.getLogger("oracle")
logger.setLevel(logging.INFO)

if not logger.handlers:
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    arquivo = logging.FileHandler(LOG_FILE, encoding="utf-8")
    arquivo.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(arquivo)

estatisticas = {
    "chamadas_modelo": 0,
    "tokens_prompt": 0,
    "tokens_completion": 0,
    "tokens_total": 0,
    "custo_total": 0.0,
    "erros": 0,
    "trocas_modelo": 0,
}

def registrar_modelo(
    modelo: str, prompt_tokens: int, completion_tokens: int,
    total_tokens: int, cached_tokens: int, duracao: float, custo: float,
) -> None:
    estatisticas["chamadas_modelo"] += 1
    estatisticas["tokens_prompt"] += prompt_tokens
    estatisticas["tokens_completion"] += completion_tokens
    estatisticas["tokens_total"] += total_tokens
    estatisticas["custo_total"] += custo
    logger.info(
        "MODELO | modelo=%s | prompt=%d | completion=%d | "
        "total=%d | cache=%d | custo=US$%.6f | tempo=%.2fs",
        modelo,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        cached_tokens,
        custo,
        duracao
    )

def registrar_troca_modelo(anterior: str, novo: str) -> None:
    estatisticas["trocas_modelo"] += 1
    logger.warning(
        "MODELO | limite atingido | anterior=%s | novo=%s",
        anterior,
        novo
    )

def registrar_erro(mensagem: str) -> None:
    estatisticas["erros"] += 1
    logger.error("ERRO | %s", mensagem)

def registrar_tool(nome: str, duracao: float, sucesso: bool) -> None:
    logger.info(
        "TOOL | nome=%s | sucesso=%s | tempo=%.2fs",
        nome,
        sucesso,
        duracao
    )

def registrar_analise(repositorio: str, arquivo: str) -> None:
    logger.info(
        "ANALISE | repositorio=%s | arquivo=%s",
        repositorio,
        arquivo
    )

def registrar_conhecimento(repositorio: str, arquivo: str) -> None:
    logger.info(
        "CONHECIMENTO | repositorio=%s | arquivo=%s",
        repositorio,
        arquivo
    )

def resumo_sessao() -> str:
    return (
        "SESSAO | "
        f"chamadas_modelo={estatisticas['chamadas_modelo']} | "
        f"prompt_tokens={estatisticas['tokens_prompt']} | "
        f"completion_tokens={estatisticas['tokens_completion']} | "
        f"total_tokens={estatisticas['tokens_total']} | "
        f"custo=US${estatisticas['custo_total']:.6f} | "
        f"erros={estatisticas['erros']}"
    )