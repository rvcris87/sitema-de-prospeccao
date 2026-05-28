import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from database import generate_message


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
GOOGLE_PLACES_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"

# Para mudar os campos buscados na API, edite este FieldMask.
GOOGLE_PLACES_FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.nationalPhoneNumber,"
    "places.websiteUri,"
    "places.rating,"
    "places.userRatingCount,"
    "places.googleMapsUri"
)


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
    """Configure the key in .env: GOOGLE_PLACES_API_KEY=sua_chave_aqui."""
    load_env_file()
    return os.getenv("GOOGLE_PLACES_API_KEY", "").strip()


def normalize_limit(value, default=20, maximum=20):
    """Altere o maximum se quiser permitir mais leads por busca."""
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(limit, maximum))


def search_google_places(nicho, cidade, limite):
    api_key = get_google_places_api_key()
    if not api_key:
        return {
            "ok": False,
            "message": "Configure a chave no arquivo .env usando GOOGLE_PLACES_API_KEY=sua_chave_aqui.",
            "leads": [],
        }

    payload = {
        "textQuery": f"{nicho} em {cidade}",
        "languageCode": "pt-BR",
        "regionCode": "BR",
        "maxResultCount": normalize_limit(limite),
    }
    request = urllib.request.Request(
        GOOGLE_PLACES_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": GOOGLE_PLACES_FIELD_MASK,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")
        return {
            "ok": False,
            "message": f"A Google Places API retornou erro {error.code}. {extract_error_message(detail)}",
            "leads": [],
        }
    except urllib.error.URLError as error:
        return {
            "ok": False,
            "message": f"Não foi possível conectar à Google Places API: {error.reason}",
            "leads": [],
        }
    except TimeoutError:
        return {
            "ok": False,
            "message": "A busca demorou demais. Tente novamente com um limite menor.",
            "leads": [],
        }

    places = data.get("places", [])
    leads = [place_to_lead(place, nicho, cidade) for place in places]
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
    return detail.get("error", {}).get("message", "Verifique a chave, billing e permissões da API.")


def place_to_lead(place, nicho, cidade):
    name = place.get("displayName", {}).get("text", "Empresa sem nome")
    phone = place.get("nationalPhoneNumber", "")
    site = place.get("websiteUri", "")
    address = place.get("formattedAddress", "")
    rating = place.get("rating")
    rating_count = place.get("userRatingCount")
    quality = "Site encontrado" if site else "Não tem site"

    if site:
        prioridade = "Baixa"
        diagnostico = "Baixa prioridade: empresa encontrada no Google Places já possui site."
    elif phone:
        prioridade = "Alta"
        diagnostico = "Alta prioridade: empresa encontrada sem site e com telefone disponível."
    else:
        prioridade = "Média"
        diagnostico = "Média prioridade: empresa sem site, mas sem telefone público na busca."

    observacoes = build_observations(address, rating, rating_count)
    lead = {
        "place_id": place.get("id", ""),
        "nome_empresa": name,
        "nicho": nicho,
        "cidade": cidade,
        "telefone_whatsapp": phone,
        "instagram": "",
        "site": site,
        "google_maps_url": place.get("googleMapsUri", ""),
        "endereco": address,
        "avaliacao": rating,
        "qtd_avaliacoes": rating_count,
        "origem_lead": "Google Places",
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
