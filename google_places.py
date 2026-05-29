import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from database import generate_message


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
APIFY_BASE_URL = "https://api.apify.com/v2"
DEFAULT_APIFY_ACTOR_ID = "compass/crawler-google-places"


def load_env_file():
    """Load .env values without requiring an extra dependency."""
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        clean_line = line.strip()
        if not clean_line or clean_line.startswith("#") or "=" not in clean_line:
            continue
        key, value = clean_line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_google_places_api_key():
    """Compatibilidade antiga: agora usa APIFY_API_TOKEN no .env."""
    load_env_file()
    token = os.getenv("APIFY_API_TOKEN", "").strip()
    if token:
        return token
    # fallback legado para não quebrar ambientes antigos
    return os.getenv("GOOGLE_PLACES_API_KEY", "").strip()


def normalize_limit(value, default=20, maximum=20):
    """Altere o maximum se quiser permitir mais leads por busca."""
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(limit, maximum))


def search_google_places(nicho, cidade, limite):
    api_token = get_google_places_api_key()
    if not api_token:
        return {
            "ok": False,
            "message": "Configure o token no arquivo .env usando APIFY_API_TOKEN=seu_token.",
            "leads": [],
        }

    actor_id = os.getenv("APIFY_GOOGLE_MAPS_ACTOR_ID", DEFAULT_APIFY_ACTOR_ID).strip()
    query = f"{nicho} em {cidade}, Brasil"
    payload = {
        "searchStringsArray": [query],
        "maxCrawledPlacesPerSearch": normalize_limit(limite),
        "language": "pt-BR",
    }
    endpoint = (
        f"{APIFY_BASE_URL}/acts/{urllib.parse.quote(actor_id, safe='/')}"
        f"/run-sync-get-dataset-items?token={urllib.parse.quote(api_token)}"
    )
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")
        return {
            "ok": False,
            "message": f"A API da Apify retornou erro {error.code}. {extract_error_message(detail)}",
            "leads": [],
        }
    except urllib.error.URLError as error:
        return {
            "ok": False,
            "message": f"Não foi possível conectar à API da Apify: {error.reason}",
            "leads": [],
        }
    except TimeoutError:
        return {
            "ok": False,
            "message": "A busca demorou demais. Tente novamente com um limite menor.",
            "leads": [],
        }

    items = data if isinstance(data, list) else []
    leads = [place_to_lead(item, nicho, cidade) for item in items]
    return {
        "ok": True,
        "message": "" if leads else "Nenhum lead encontrado para essa busca.",
        "leads": leads,
    }


def extract_error_message(raw_detail):
    try:
        detail = json.loads(raw_detail)
    except json.JSONDecodeError:
        return raw_detail[:220]
    if isinstance(detail, dict):
        if detail.get("error", {}).get("message"):
            return detail["error"]["message"]
        if detail.get("message"):
            return detail["message"]
    return "Verifique APIFY_API_TOKEN e APIFY_GOOGLE_MAPS_ACTOR_ID no .env."


def place_to_lead(place, nicho, cidade):
    name = place.get("title") or place.get("name") or "Empresa sem nome"
    phone = place.get("phone") or place.get("phoneUnformatted") or ""
    site = place.get("website") or ""
    address = place.get("address") or place.get("street") or ""
    rating = place.get("totalScore")
    rating_count = place.get("reviewsCount")
    quality = "Site encontrado" if site else "Não tem site"

    if site:
        prioridade = "Baixa"
        diagnostico = "Baixa prioridade: empresa encontrada pela Apify já possui site."
    elif phone:
        prioridade = "Alta"
        diagnostico = "Alta prioridade: empresa encontrada sem site e com telefone disponível."
    else:
        prioridade = "Média"
        diagnostico = "Média prioridade: empresa sem site, mas sem telefone público na busca."

    observacoes = build_observations(address, rating, rating_count)
    lead = {
        "place_id": place.get("placeId", "") or place.get("id", ""),
        "nome_empresa": name,
        "nicho": nicho,
        "cidade": cidade,
        "telefone_whatsapp": phone,
        "instagram": "",
        "site": site,
        "google_maps_url": place.get("url", "") or place.get("googleMapsUri", ""),
        "endereco": address,
        "avaliacao": rating,
        "qtd_avaliacoes": rating_count,
        "origem_lead": "Apify",
        "observacoes": observacoes,
        "status": "Novo",
        "qualidade_site": quality,
        "prioridade": prioridade,
        "diagnostico": diagnostico,
    }
    lead["mensagem"] = generate_message(lead)
    return lead


def build_observations(address, rating, rating_count):
    parts = []
    if address:
        parts.append(f"Endereço: {address}")
    if rating:
        parts.append(f"Avaliação: {rating}")
    if rating_count is not None:
        parts.append(f"Quantidade de avaliações: {rating_count}")
    return "\n".join(parts)
