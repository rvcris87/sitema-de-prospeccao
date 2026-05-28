import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "leads.db"


STATUS_OPTIONS = [
    "Novo",
    "Analisado",
    "Mensagem enviada",
    "Respondeu",
    "Proposta enviada",
    "Fechado",
    "Recusado",
]

SITE_QUALITY_OPTIONS = [
    "Não tem site",
    "Só rede social",
    "Site encontrado",
    "Site ruim",
    "Site mediano",
    "Site bom",
]

PRIORITY_OPTIONS = ["Alta", "Média", "Baixa"]


def get_connection():
    """Open a SQLite connection prepared to return rows as dictionaries."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create and migrate the leads table if this is the first application run."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_empresa TEXT NOT NULL,
                nicho TEXT NOT NULL,
                cidade TEXT NOT NULL,
                telefone_whatsapp TEXT,
                instagram TEXT,
                site TEXT,
                observacoes TEXT,
                endereco TEXT,
                estado TEXT,
                google_maps_url TEXT,
                avaliacao REAL,
                qtd_avaliacoes INTEGER,
                origem_lead TEXT,
                status TEXT NOT NULL DEFAULT 'Novo',
                qualidade_site TEXT NOT NULL DEFAULT 'Não tem site',
                prioridade TEXT NOT NULL DEFAULT 'Alta',
                diagnostico TEXT NOT NULL,
                mensagem TEXT NOT NULL,
                ai_analisado INTEGER DEFAULT 0,
                ai_potencial TEXT,
                ai_motivo TEXT,
                ai_sugestao TEXT,
                ia_real_resultado TEXT,
                ia_real_score INTEGER,
                ia_real_potencial TEXT,
                ia_real_fontes TEXT,
                analisado_em TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        migrate_db(connection)


def migrate_db(connection):
    """Add new columns without losing existing SQLite data."""
    current_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(leads)").fetchall()
    }
    migrations = {
        "endereco": "ALTER TABLE leads ADD COLUMN endereco TEXT",
        "estado": "ALTER TABLE leads ADD COLUMN estado TEXT",
        "google_maps_url": "ALTER TABLE leads ADD COLUMN google_maps_url TEXT",
        "avaliacao": "ALTER TABLE leads ADD COLUMN avaliacao REAL",
        "qtd_avaliacoes": "ALTER TABLE leads ADD COLUMN qtd_avaliacoes INTEGER",
        "origem_lead": "ALTER TABLE leads ADD COLUMN origem_lead TEXT",
        "ai_analisado": "ALTER TABLE leads ADD COLUMN ai_analisado INTEGER DEFAULT 0",
        "ai_potencial": "ALTER TABLE leads ADD COLUMN ai_potencial TEXT",
        "ai_motivo": "ALTER TABLE leads ADD COLUMN ai_motivo TEXT",
        "ai_sugestao": "ALTER TABLE leads ADD COLUMN ai_sugestao TEXT",
        "ia_real_resultado": "ALTER TABLE leads ADD COLUMN ia_real_resultado TEXT",
        "ia_real_score": "ALTER TABLE leads ADD COLUMN ia_real_score INTEGER",
        "ia_real_potencial": "ALTER TABLE leads ADD COLUMN ia_real_potencial TEXT",
        "ia_real_fontes": "ALTER TABLE leads ADD COLUMN ia_real_fontes TEXT",
        "analisado_em": "ALTER TABLE leads ADD COLUMN analisado_em TEXT",
    }

    for column, statement in migrations.items():
        if column not in current_columns:
            connection.execute(statement)


def normalize_url(value):
    """Return a usable URL for links, keeping empty fields empty."""
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    return f"https://{value}"


def normalize_instagram(value):
    """Accept @perfil, perfil or a full Instagram URL and return a profile URL."""
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    handle = value.replace("@", "").strip("/")
    return f"https://instagram.com/{handle}"


def only_digits(value):
    """Keep only numbers for WhatsApp links."""
    return "".join(character for character in (value or "") if character.isdigit())


def whatsapp_link(value):
    """Build a Brazilian WhatsApp link with only digits."""
    digits = only_digits(value)
    if not digits:
        return ""
    if not digits.startswith("55"):
        digits = f"55{digits}"
    return f"https://wa.me/{digits}"


def diagnose_lead(qualidade_site, telefone_whatsapp="", instagram="", site=""):
    """Classify the lead with a simple, explainable scoring rule."""
    has_contact = bool((telefone_whatsapp or "").strip() or (instagram or "").strip())
    site_quality = qualidade_site or "Não tem site"

    if site_quality == "Não tem site" and has_contact:
        return {
            "prioridade": "Alta",
            "diagnostico": "Alta prioridade: empresa sem site próprio e com canal direto para abordagem.",
        }

    if site_quality == "Só rede social":
        return {
            "prioridade": "Alta",
            "diagnostico": "Alta prioridade: empresa usa apenas rede social ou link de contato no lugar de site próprio.",
        }

    if site_quality in ("Site ruim", "Site mediano"):
        return {
            "prioridade": "Média",
            "diagnostico": "Média prioridade: já existe um site, mas há espaço para melhorar a presença digital.",
        }

    if site_quality in ("Site bom", "Site encontrado"):
        return {
            "prioridade": "Baixa",
            "diagnostico": "Baixa prioridade: a empresa já possui site e pode ser avaliada depois.",
        }

    if (site or "").strip():
        return {
            "prioridade": "Média",
            "diagnostico": "Média prioridade: lead possui site e precisa de uma avaliação mais cuidadosa.",
        }

    return {
        "prioridade": "Baixa",
        "diagnostico": "Baixa prioridade: faltam canais claros de contato para uma abordagem imediata.",
    }


def generate_message(lead):
    """Create a personalized WhatsApp/Instagram approach message."""
    nome = lead.get("nome_empresa", "sua empresa")
    nicho = lead.get("nicho", "segmento")
    cidade = lead.get("cidade", "sua cidade")
    qualidade_site = lead.get("qualidade_site", "Não tem site")
    prioridade = lead.get("prioridade") or diagnose_lead(
        qualidade_site,
        lead.get("telefone_whatsapp", ""),
        lead.get("instagram", ""),
        lead.get("site", ""),
    )["prioridade"]

    if qualidade_site in ("Não tem site", "Só rede social"):
        return (
            f"Oi, tudo bem? Me chamo Cristine, sou desenvolvedora de sites. "
            f"Vi a {nome}, que atua com {nicho} em {cidade}, e percebi uma oportunidade de vocês terem um site próprio. "
            "Um site simples pode ajudar clientes a conhecerem serviços, localização, horários e formas de contato. "
            "Posso te mostrar uma ideia de página profissional para vocês?"
        )

    if qualidade_site in ("Site ruim", "Site mediano"):
        return (
            f"Oi, tudo bem? Me chamo Cristine, sou desenvolvedora de sites. "
            f"Conheci a {nome}, de {nicho} em {cidade}, e vi uma oportunidade de deixar o site mais moderno, rápido e claro para os clientes. "
            "Posso te enviar uma sugestão simples de melhoria para aumentar a confiança de quem encontra vocês online?"
        )

    return (
        f"Oi, tudo bem? Me chamo Cristine, sou desenvolvedora de sites. "
        f"Vi a {nome}, de {nicho} em {cidade}, e gostei da presença digital de vocês. "
        f"Como o lead está em prioridade {prioridade.lower()}, queria me apresentar para futuras melhorias, páginas promocionais ou ajustes no site quando fizer sentido."
    )


def prepare_lead_payload(form):
    """Transform form data into a complete lead payload for saving."""
    payload = {
        "nome_empresa": form.get("nome_empresa", "").strip(),
        "nicho": form.get("nicho", "").strip(),
        "cidade": form.get("cidade", "").strip(),
        "telefone_whatsapp": form.get("telefone_whatsapp", "").strip(),
        "instagram": form.get("instagram", "").strip(),
        "site": form.get("site", "").strip(),
        "observacoes": form.get("observacoes", "").strip(),
        "endereco": form.get("endereco", "").strip(),
        "estado": form.get("estado", "").strip(),
        "google_maps_url": form.get("google_maps_url", "").strip(),
        "avaliacao": form.get("avaliacao") or None,
        "qtd_avaliacoes": form.get("qtd_avaliacoes") or None,
        "origem_lead": form.get("origem_lead", "").strip(),
        "status": form.get("status", "Novo").strip() or "Novo",
        "qualidade_site": form.get("qualidade_site", "Não tem site").strip() or "Não tem site",
    }
    diagnosis = diagnose_lead(
        payload["qualidade_site"],
        payload["telefone_whatsapp"],
        payload["instagram"],
        payload["site"],
    )
    payload.update(diagnosis)
    payload["mensagem"] = generate_message(payload)
    return payload


def create_lead(payload):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO leads (
                nome_empresa, nicho, cidade, telefone_whatsapp, instagram, site,
                observacoes, endereco, estado, google_maps_url, avaliacao, qtd_avaliacoes, origem_lead,
                status, qualidade_site, prioridade, diagnostico, mensagem
            )
            VALUES (
                :nome_empresa, :nicho, :cidade, :telefone_whatsapp, :instagram, :site,
                :observacoes, :endereco, :estado, :google_maps_url, :avaliacao, :qtd_avaliacoes, :origem_lead,
                :status, :qualidade_site, :prioridade, :diagnostico, :mensagem
            )
            """,
            with_extended_defaults(payload),
        )
        return cursor.lastrowid


def update_lead(lead_id, payload):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE leads
            SET nome_empresa = :nome_empresa,
                nicho = :nicho,
                cidade = :cidade,
                telefone_whatsapp = :telefone_whatsapp,
                instagram = :instagram,
                site = :site,
                observacoes = :observacoes,
                endereco = :endereco,
                estado = :estado,
                google_maps_url = :google_maps_url,
                avaliacao = :avaliacao,
                qtd_avaliacoes = :qtd_avaliacoes,
                origem_lead = :origem_lead,
                status = :status,
                qualidade_site = :qualidade_site,
                prioridade = :prioridade,
                diagnostico = :diagnostico,
                mensagem = :mensagem,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
            """,
            {**with_extended_defaults(payload), "id": lead_id},
        )


def delete_lead(lead_id):
    with get_connection() as connection:
        connection.execute("DELETE FROM leads WHERE id = ?", (lead_id,))


def get_lead(lead_id):
    with get_connection() as connection:
        return connection.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()


def list_leads(filters=None):
    """List leads using optional dashboard filters."""
    filters = filters or {}
    query = "SELECT * FROM leads WHERE 1 = 1"
    params = {}

    for field in ("nicho", "cidade", "prioridade", "status"):
        value = (filters.get(field) or "").strip()
        if value:
            query += f" AND {field} = :{field}"
            params[field] = value

    site_filter = (filters.get("site_filter") or "").strip()
    if site_filter == "tem_site":
        query += " AND TRIM(COALESCE(site, '')) != '' AND qualidade_site != 'Não tem site'"
    elif site_filter == "sem_site":
        query += " AND (TRIM(COALESCE(site, '')) = '' OR qualidade_site = 'Não tem site')"

    query += """
        ORDER BY
            CASE prioridade
                WHEN 'Alta' THEN 1
                WHEN 'Média' THEN 2
                ELSE 3
            END,
            updated_at DESC
    """

    with get_connection() as connection:
        return connection.execute(query, params).fetchall()


def with_extended_defaults(payload):
    """Keep old manual leads and imported leads compatible with the same insert/update."""
    defaults = {
        "endereco": "",
        "estado": "",
        "google_maps_url": "",
        "avaliacao": None,
        "qtd_avaliacoes": None,
        "origem_lead": "",
    }
    return {**defaults, **payload}


def lead_exists(payload):
    """Avoid duplicates by phone, site, Google Maps URL or name+city before importing."""
    nome_empresa = (payload.get("nome_empresa") or "").strip()
    cidade = (payload.get("cidade") or "").strip()
    telefone_options = normalize_phone_options(payload.get("telefone_whatsapp") or "")
    site = normalize_site_for_duplicate(payload.get("site") or "")
    google_maps_url = normalize_url_for_duplicate(payload.get("google_maps_url") or "")

    conditions = []
    params = {}

    if nome_empresa and cidade:
        conditions.append("(LOWER(nome_empresa) = LOWER(:nome_empresa) AND LOWER(cidade) = LOWER(:cidade))")
        params["nome_empresa"] = nome_empresa
        params["cidade"] = cidade

    if telefone_options:
        conditions.append("REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(telefone_whatsapp, '+', ''), ' ', ''), '-', ''), '(', ''), ')', ''), '.', ''), '/', '') IN (:telefone, :telefone_sem_pais, :telefone_com_pais)")
        params["telefone"] = telefone_options["original"]
        params["telefone_sem_pais"] = telefone_options["sem_pais"]
        params["telefone_com_pais"] = telefone_options["com_pais"]

    if site:
        conditions.append("LOWER(RTRIM(REPLACE(REPLACE(site, 'https://', ''), 'http://', ''), '/')) = :site")
        params["site"] = site

    if google_maps_url:
        conditions.append("LOWER(RTRIM(REPLACE(REPLACE(google_maps_url, 'https://', ''), 'http://', ''), '/')) = :google_maps_url")
        params["google_maps_url"] = google_maps_url

    if not conditions:
        return False

    with get_connection() as connection:
        query = f"SELECT id FROM leads WHERE {' OR '.join(conditions)} LIMIT 1"
        return connection.execute(query, params).fetchone() is not None


def create_lead_if_not_duplicate(payload):
    """Insert a lead only when it is not already in the CRM."""
    if lead_exists(payload):
        return {"saved": False, "reason": "duplicado", "id": None}
    lead_id = create_lead(payload)
    return {"saved": True, "reason": "salvo", "id": lead_id}


def normalize_site_for_duplicate(value):
    return normalize_url_for_duplicate(value)


def normalize_url_for_duplicate(value):
    value = normalize_url(value).lower().strip().rstrip("/")
    return value.replace("https://", "").replace("http://", "")


def normalize_phone_options(value):
    digits = only_digits(value)
    if not digits:
        return {}
    without_country = digits[2:] if digits.startswith("55") and len(digits) > 11 else digits
    with_country = digits if digits.startswith("55") else f"55{digits}"
    return {
        "original": digits,
        "sem_pais": without_country,
        "com_pais": with_country,
    }


def distinct_values(field):
    allowed_fields = {"nicho", "cidade", "prioridade", "status"}
    if field not in allowed_fields:
        return []

    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT DISTINCT {field} FROM leads WHERE TRIM({field}) != '' ORDER BY {field}"
        ).fetchall()
        return [row[field] for row in rows]
