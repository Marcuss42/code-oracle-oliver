import configparser
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")


config = configparser.ConfigParser()
config.read(
    BASE_DIR / "ai" / "config" / "config.ini",
    encoding="utf-8"
)


PROVEDOR = config["modelo"]["provedor"]
CONFIG_PROVEDOR = config[PROVEDOR]

MODEL = CONFIG_PROVEDOR["modelo"]
BASE_URL = CONFIG_PROVEDOR["base_url"]


# Monta o nome da variável automaticamente:
# gemini -> GEMINI_API_KEY
# groq   -> GROQ_API_KEY
API_KEY_ENV = f"{PROVEDOR.upper()}_API_KEY"

api_key = os.getenv(API_KEY_ENV)

if not api_key:
    raise RuntimeError(
        f"{API_KEY_ENV} não configurada."
    )


PRECOS = {
    config[secao]["modelo"]: {
        "entrada": config.getfloat(secao, "entrada"),
        "entrada_cache": config.getfloat(secao, "entrada_cache"),
        "saida": config.getfloat(secao, "saida")
    }
    for secao in config.sections()
    if secao != "modelo"
    and config.has_option(secao, "modelo")
    and config.has_option(secao, "entrada")
}


client = OpenAI(
    base_url=BASE_URL,
    api_key=api_key,
    timeout=120
)