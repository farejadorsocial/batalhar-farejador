"""
Inicializador do backend.

Pode ser executado diretamente dentro da pasta backend:
    python run.py

As dependências ausentes são instaladas automaticamente pelo requirements.txt.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REQUIREMENTS = BASE_DIR / "requirements.txt"


def _dependencias_faltantes():
    modulos = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "sqlalchemy": "sqlalchemy",
        "pydantic_settings": "pydantic-settings",
        "jwt": "PyJWT",
        "argon2": "argon2-cffi",
        "multipart": "python-multipart",
        "email_validator": "email-validator",
    }
    return [pacote for modulo, pacote in modulos.items()
            if importlib.util.find_spec(modulo) is None]


def _instalar_dependencias():
    faltantes = _dependencias_faltantes()
    if not faltantes:
        return

    print("Dependências ausentes:", ", ".join(faltantes))
    print("Instalando pelo requirements.txt...")
    comando = [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)]
    try:
        subprocess.run(comando, check=True)
    except subprocess.CalledProcessError:
        subprocess.run(comando + ["--user"], check=True)


_instalar_dependencias()

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("FAREJADOR_HOST", "127.0.0.1"),
        port=int(os.getenv("FAREJADOR_PORT", "8010")),
        reload=os.getenv("FAREJADOR_RELOAD", "1") == "1",
    )
