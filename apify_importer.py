import csv
from io import TextIOWrapper
from urllib.parse import urlparse

from database import create_lead_if_not_duplicate, generate_message, only_digits


EMPTY_VALUES = {"", "null", "none", "undefined", "nan"}
SOCIAL_DOMAINS = (
    "facebook.com",
    "fb.com",
    "instagram.com",
    "linktr.ee",
    "linktree.com",
    "wa.me",
    "whatsapp.com",
    "api.whatsapp.com",
)


def import_apify_csv(file_storage):
    """Read an Apify Google Maps Scraper CSV and save valid, non-duplicate leads."""
    summary = {
        "total_linhas": 0,
        "importados": 0,
        "duplicados": 0,
        "erros": 0,
        "mensagens_erro": [],
    }

    stream = TextIOWrapper(file_storage.stream, encoding="utf-8-sig", newline="")
    reader = csv.DictReader(stream)

    if not reader.fieldnames:
        summary["erros"] = 1
        summary["mensagens_erro"].append("O CSV está vazio ou sem cabeçalho.")
        return summary

    for row_number, row in enumerate(reader, start=2):
        summary["total_linhas"] += 1
        try:
            lead = apify_row_to_lead(row)
            if not lead["nome_empresa"]:
                raise ValueError("linha sem nome da empresa")

            result = create_lead_if_not_duplicate(lead)
            if result["saved"]:
                summary["importados"] += 1
            else:
                summary["duplicados"] += 1
        except Exception as error:
            summary["erros"] += 1
            summary["mensagens_erro"].append(f"Linha {row_number}: {error}")

    return summary


def apify_row_to_lead(row):
    nome = first_value(row, "title", "name")
    nicho = first_value(row, "categoryName", "category") or "Não informado"
    endereco = first_value(row, "street", "address")
    cidade = first_value(row, "city") or "Não informada"
    estado = first_value(row, "state")
    telefone = first_value(row, "phone")
    site = first_value(row, "website")
    google_maps_url = first_value(row, "url")
    avaliacao = parse_float(first_value(row, "totalScore"))
    qtd_avaliacoes = parse_int(first_value(row, "reviewsCount"))

    quality, priority, diagnosis = diagnose_apify_site(site, telefone)
    observacoes = build_observations(endereco, cidade, estado, avaliacao, qtd_avaliacoes)

    lead = {
        "nome_empresa": nome,
        "nicho": nicho,
        "cidade": cidade,
        "telefone_whatsapp": telefone,
        "instagram": "",
        "site": site,
        "observacoes": observacoes,
        "endereco": endereco,
        "estado": estado,
        "google_maps_url": google_maps_url,
        "avaliacao": avaliacao,
        "qtd_avaliacoes": qtd_avaliacoes,
        "origem_lead": "Apify Google Maps",
        "status": "Novo",
        "qualidade_site": quality,
        "prioridade": priority,
        "diagnostico": diagnosis,
    }
    lead["mensagem"] = generate_message(lead)
    return lead


def first_value(row, *columns):
    for column in columns:
        for key, value in row.items():
            if key and key.strip() == column:
                return clean_value(value)
    return ""


def clean_value(value):
    value = str(value or "").strip()
    if value.lower() in EMPTY_VALUES:
        return ""
    return value


def diagnose_apify_site(site, telefone):
    if is_social_or_contact_url(site):
        return (
            "Só rede social",
            "Alta",
            "Alta prioridade: a empresa usa rede social ou WhatsApp como presença principal, sem site próprio.",
        )

    if not site:
        if only_digits(telefone):
            return (
                "Não tem site",
                "Alta",
                "Alta prioridade: empresa importada sem site e com telefone disponível.",
            )
        return (
            "Não tem site",
            "Média",
            "Média prioridade: empresa importada sem site e sem telefone público.",
        )

    return (
        "Site encontrado",
        "Baixa",
        "Baixa prioridade: empresa importada com site próprio encontrado.",
    )


def is_social_or_contact_url(site):
    if not site:
        return False
    parsed = urlparse(site if "://" in site else f"https://{site}")
    host = parsed.netloc.lower().replace("www.", "")
    return any(host == domain or host.endswith(f".{domain}") for domain in SOCIAL_DOMAINS)


def parse_float(value):
    value = clean_value(value).replace(",", ".")
    if not value:
        return None
    return float(value)


def parse_int(value):
    value = clean_value(value)
    if not value:
        return None
    return int(float(value.replace(",", ".")))


def build_observations(endereco, cidade, estado, avaliacao, qtd_avaliacoes):
    parts = []
    if endereco:
        parts.append(f"Endereço: {endereco}")
    location = " - ".join(part for part in (cidade, estado) if part)
    if location:
        parts.append(f"Localidade: {location}")
    if avaliacao is not None:
        parts.append(f"Avaliação: {avaliacao}")
    if qtd_avaliacoes is not None:
        parts.append(f"Quantidade de avaliações: {qtd_avaliacoes}")
    return "\n".join(parts)
