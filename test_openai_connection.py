import os
import socket
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


def load_env_file():
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def print_result(title, ok, detail):
    status = "OK" if ok else "FALHA"
    print(f"[{status}] {title}: {detail}")


def test_env_key():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return False, "OPENAI_API_KEY não encontrada no ambiente."
    if key == "sua_chave_aqui":
        return False, "OPENAI_API_KEY está com valor placeholder."
    return True, "OPENAI_API_KEY definida."


def test_network_access():
    try:
        socket.gethostbyname("api.openai.com")
        req = urllib.request.Request("https://api.openai.com/v1/models", method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            code = response.getcode()
            return True, f"Conexão HTTPS estabelecida (HTTP {code})."
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return True, f"Host acessível (HTTP {e.code} esperado sem auth)."
        return False, f"HTTPError inesperado: {e}"
    except Exception as e:
        return False, f"Falha de rede ao acessar api.openai.com: {e}"


def test_minimal_openai_call():
    try:
        from openai import OpenAI
    except Exception as e:
        return False, f"SDK openai indisponível: {e}"

    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return False, "Sem OPENAI_API_KEY para chamada mínima."

    try:
        client = OpenAI(api_key=key)
        response = client.responses.create(
            model="gpt-4o-mini",
            input="Responda apenas: ok",
            max_output_tokens=16,
        )
        output = (response.output_text or "").strip()
        return True, f"Chamada mínima concluída. Saída: {output or '(vazia)'}"
    except Exception as e:
        return False, f"Falha na chamada mínima: {e}"


def main():
    load_env_file()
    print("Teste de conectividade OpenAI\n")
    checks = [
        ("Variável OPENAI_API_KEY", test_env_key),
        ("Acesso de rede a api.openai.com", test_network_access),
        ("Chamada mínima à OpenAI", test_minimal_openai_call),
    ]
    failed = 0
    for title, fn in checks:
        ok, detail = fn()
        print_result(title, ok, detail)
        if not ok:
            failed += 1

    print("")
    if failed:
        print("Resultado final: ambiente com pendências para OpenAI.")
        raise SystemExit(1)
    print("Resultado final: ambiente apto para OpenAI.")


if __name__ == "__main__":
    main()
