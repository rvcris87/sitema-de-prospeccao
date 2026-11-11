import os
import traceback
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for, session
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from functools import wraps
from collections import Counter
from urllib.parse import quote
import json
import sqlite3
import unicodedata

from icons import icon

BOOT_IMPORT_ERROR = None
try:
    from apify_importer import import_apify_csv
    from database import (
        SITE_QUALITY_OPTIONS,
        STATUS_OPTIONS,
        create_lead_if_not_duplicate,
        create_lead,
        delete_lead,
        distinct_values,
        get_lead,
        init_db,
        list_leads,
        normalize_instagram,
        normalize_url,
        only_digits,
        prepare_lead_payload,
        update_lead,
        whatsapp_link,
        get_connection,
    )
    from google_places import get_google_places_api_key, normalize_limit, search_google_places
    from ia_real_service import execute_real_ai_analysis, get_current_limit_info
except Exception as exc:
    BOOT_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "radar-local-secret-key-123")
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
if os.getenv("RAILWAY_PUBLIC_DOMAIN"):
    app.config["SESSION_COOKIE_SECURE"] = True

# Railway and other reverse proxies forward protocol/host headers.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.before_request
def atualizar_plano_da_sessao():
    """Relê o plano no banco a cada request logado, para o topo não mostrar um plano antigo."""
    if not session.get("logged_in") or request.endpoint == "static":
        return
    email = session.get("user_email")
    if not email:
        return
    try:
        user = get_user_by_email(email)
    except sqlite3.Error:
        return  # Banco indisponível: mantém o que já está na sessão.
    if user and session.get("user_plan") != user["plano"]:
        session["user_plan"] = user["plano"]


@app.context_processor
def utility_processor():
    current_user = {
        "nome": session.get("user_name", "Usuário"),
        "email": session.get("user_email", ""),
        "plano": session.get("user_plan", "Plano Inicial"),
    }
    return {
        "normalize_url": normalize_url,
        "normalize_instagram": normalize_instagram,
        "only_digits": only_digits,
        "whatsapp_link": whatsapp_link,
        "icon": icon,
        "current_user": current_user,
        "montar_presenca": montar_presenca,
    }


def get_user_by_email(email):
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE lower(email) = lower(?)",
            (email,),
        ).fetchone()


def create_user(nome, email, senha):
    senha_hash = generate_password_hash(senha)
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO users (nome, email, senha_hash) VALUES (?, ?, ?)",
            (nome, email, senha_hash),
        )
        return cursor.lastrowid


def authenticate_user(email, senha):
    user = get_user_by_email(email)
    if not user:
        return None
    if not check_password_hash(user["senha_hash"], senha):
        return None
    return user


@app.route("/")
def landing():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/health")
def health():
    db_error = app.config.get("DB_INIT_ERROR")
    import_error = BOOT_IMPORT_ERROR
    return {
        "ok": db_error is None and import_error is None,
        "service": "sitema-de-prospeccao",
        "db_init_error": db_error,
        "boot_import_error": import_error,
    }, 200 if (db_error is None and import_error is None) else 500


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
        
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        user = authenticate_user(email, password)
        if user:
            session["logged_in"] = True
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["user_name"] = user["nome"]
            session["user_plan"] = user["plano"]
            flash("Login realizado com sucesso! Bem-vindo ao painel.", "success")
            return redirect(url_for("dashboard"))
        flash("Credenciais inválidas. Verifique e tente novamente.", "error")
            
    return render_template("login.html")


@app.route("/cadastro", methods=["GET", "POST"])
@app.route("/register", methods=["GET", "POST"])
def cadastro():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "").strip()
        confirmar_senha = request.form.get("confirmar_senha", "").strip()

        if not nome or not email or not senha:
            flash("Preencha nome, e-mail e senha para criar sua conta.", "error")
            return render_template("register.html")
        if senha != confirmar_senha:
            flash("A confirmação de senha não confere.", "error")
            return render_template("register.html")
        if get_user_by_email(email):
            flash("Já existe uma conta com este e-mail.", "error")
            return render_template("register.html")

        create_user(nome, email, senha)
        flash("Conta criada com sucesso! Faça login para continuar.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/demo-login")
def demo_login():
    demo_email = "demo@radarlocal.com"
    demo_user = get_user_by_email(demo_email)
    if not demo_user:
        create_user("Demonstração", demo_email, "123456")
        demo_user = get_user_by_email(demo_email)

    session["logged_in"] = True
    session["user_id"] = demo_user["id"]
    session["user_email"] = demo_user["email"]
    session["user_name"] = demo_user["nome"]
    session["user_plan"] = demo_user["plano"]
    flash("Acesso de demonstração ativado!", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Sessão encerrada com sucesso.", "success")
    return redirect(url_for("landing"))


FILTER_KEYS = (
    "q",
    "nicho",
    "cidade",
    "prioridade",
    "status",
    "site_filter",
    "tipo_site",
    "whatsapp_compat",
    "instagram_encontrado",
    "origem_lead",
    "data_referencia",
    "aprovacao",
)

# Campos calculados que o front precisa; _laudo fica de fora da API (já vem em ia_real_resultado).
API_LEAD_EXCLUDE = {"_laudo"}


def get_filters():
    return {key: request.args.get(key, "") for key in FILTER_KEYS}


def has_active_filters(filters):
    return any((value or "").strip() for value in filters.values())


def processar_lead(row):
    """Converte a linha do banco em dict e adiciona os campos derivados do laudo."""
    lead = dict(row)
    laudo = {}
    if lead.get("ia_real_resultado"):
        try:
            laudo = json.loads(lead.get("ia_real_resultado") or "{}")
        except Exception:
            laudo = {}

    lead["_laudo"] = laudo
    lead["_status_geral"] = (
        "Aprovado"
        if laudo.get("lead_aprovado_abordagem") == "sim"
        else "Descartado"
        if laudo.get("lead_aprovado_abordagem") == "nao"
        else "Com ressalvas"
        if laudo.get("lead_aprovado_abordagem") == "com_ressalvas"
        else "Não validado"
    )
    lead["_score"] = lead.get("ia_real_score") or laudo.get("score") or 0
    lead["_confianca"] = laudo.get("confianca_verificacao") or 0
    lead["_whatsapp_compat"] = laudo.get("compatibilidade_whatsapp") or "incerto"
    lead["_site_tipo"] = laudo.get("tipo_site") or "incerto"
    lead["_conclusao"] = (
        laudo.get("diagnostico")
        or lead.get("diagnostico")
        or "Sem conclusão de laudo para este lead."
    )
    lead["_instagram_encontrado"] = laudo.get("instagram_encontrado") or "incerto"
    lead["_validado"] = bool(lead.get("ia_real_resultado"))
    try:
        score = int(float(lead["_score"]))
    except (TypeError, ValueError):
        score = 0
    lead["_score"] = score
    # Nível usado para a cor do score: verde, amarelo, vermelho ou cinza (sem laudo).
    if not lead["_validado"] and not score:
        lead["_score_nivel"] = "nenhum"
    elif score >= 70:
        lead["_score_nivel"] = "alto"
    elif score >= 40:
        lead["_score_nivel"] = "medio"
    else:
        lead["_score_nivel"] = "baixo"
    return lead


def normalizar_busca(texto):
    """Minúsculas e sem acentos, para a busca por nome."""
    texto = unicodedata.normalize("NFKD", str(texto or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c)).strip()


def passes_advanced_filters(lead, filters):
    busca = normalizar_busca(filters.get("q"))
    if busca and busca not in normalizar_busca(lead.get("nome_empresa")):
        return False
    if filters["tipo_site"] and lead.get("_site_tipo") != filters["tipo_site"]:
        return False
    if filters["whatsapp_compat"] and lead.get("_whatsapp_compat") != filters["whatsapp_compat"]:
        return False
    if filters["instagram_encontrado"] and lead.get("_instagram_encontrado") != filters["instagram_encontrado"]:
        return False
    if filters["origem_lead"] and (lead.get("origem_lead") or "").strip() != filters["origem_lead"]:
        return False
    # aprovacao=sim: só leads cujo laudo aprovou a abordagem.
    if filters.get("aprovacao") and (lead.get("_laudo") or {}).get("lead_aprovado_abordagem") != filters["aprovacao"]:
        return False
    if filters["data_referencia"]:
        created_at = str(lead.get("created_at") or "")
        if not created_at.startswith(filters["data_referencia"]):
            return False
    return True


def get_leads_filtrados(filters=None):
    filters = filters if filters is not None else get_filters()
    leads = [processar_lead(row) for row in list_leads(filters)]
    return [lead for lead in leads if passes_advanced_filters(lead, filters)]


def get_metrics(all_leads=None):
    """Métricas de qualidade com uma única leitura dos leads.

    Aceita leads já processados (por processar_lead) para evitar nova consulta.
    """
    if all_leads is None:
        all_leads = [processar_lead(row) for row in list_leads()]

    metrics = {
        "leads_importados": len(all_leads),
        "leads_validados": 0,
        "leads_aprovados": 0,
        "leads_descartados": 0,
        "whatsapps_compativeis": 0,
        "whatsapps_incerto_suspeitos": 0,
        "sem_site": 0,
        "oportunidades_altas": 0,
        "mensagens_enviadas": 0,
        "respostas_recebidas": 0,
        "leads_com_ressalvas": 0,
        "sites_terceirizados": 0,
        # Só entre leads analisados: o laudo não encontrou site (nada ou só rede social).
        "sem_site_proprio": 0,
        "prioridade_media": 0,
        "prioridade_baixa": 0,
    }

    for lead in all_leads:
        if lead.get("status") == "Mensagem enviada":
            metrics["mensagens_enviadas"] += 1
        if lead.get("status") == "Respondeu":
            metrics["respostas_recebidas"] += 1
        if lead.get("qualidade_site") in ("Não tem site", "Só rede social"):
            metrics["sem_site"] += 1
        if not lead.get("ia_real_resultado"):
            continue
        metrics["leads_validados"] += 1

        data = lead.get("_laudo") or {}
        if data.get("compatibilidade_whatsapp") == "compativel":
            metrics["whatsapps_compativeis"] += 1
        if data.get("compatibilidade_whatsapp") in ("incerto", "divergente"):
            metrics["whatsapps_incerto_suspeitos"] += 1
        if data.get("lead_aprovado_abordagem") == "com_ressalvas":
            metrics["leads_com_ressalvas"] += 1
        if data.get("lead_aprovado_abordagem") == "nao":
            metrics["leads_descartados"] += 1
        if data.get("tipo_site") in ("site_terceirizado", "cardapio_plataforma_externa"):
            metrics["sites_terceirizados"] += 1
        if data.get("tipo_site") in SITE_TIPOS_SEM_SITE:
            metrics["sem_site_proprio"] += 1
        if data.get("lead_aprovado_abordagem") == "sim":
            metrics["leads_aprovados"] += 1
        if data.get("prioridade") == "alta":
            metrics["oportunidades_altas"] += 1
        if data.get("prioridade") == "media":
            metrics["prioridade_media"] += 1
        if data.get("prioridade") == "baixa":
            metrics["prioridade_baixa"] += 1

    return metrics


SITE_TIPOS_SEM_SITE = ("nao_encontrado", "rede_social")


def percentual(parte, total):
    return round(parte * 100 / total) if total else 0


def get_prioridade_por_cidade(all_leads, limite=6):
    """Leads analisados / total por cidade, das cidades com mais leads."""
    por_cidade = {}
    for lead in all_leads:
        cidade = (lead.get("cidade") or "").strip() or "Sem cidade"
        item = por_cidade.setdefault(cidade, {"cidade": cidade, "total": 0, "analisados": 0})
        item["total"] += 1
        if lead.get("_validado"):
            item["analisados"] += 1
    cidades = sorted(por_cidade.values(), key=lambda c: (-c["total"], c["cidade"]))[:limite]
    for item in cidades:
        item["pct"] = percentual(item["analisados"], item["total"])
    return cidades


def _mais_comum(valores):
    contagem = Counter(v for v in valores if v)
    return contagem.most_common(1)[0] if contagem else None


def gerar_insights(all_leads, metrics):
    """Frases simples calculadas dos leads reais. Lista vazia se não há laudos."""
    total = metrics["leads_importados"]
    analisados = metrics["leads_validados"]
    if not analisados:
        return []

    insights = [{
        "titulo": "Cobertura",
        "texto": f"{analisados} de {total} leads ({percentual(analisados, total)}%) já têm laudo.",
    }]

    sem_site = [l for l in all_leads if l.get("_validado") and l.get("_site_tipo") in SITE_TIPOS_SEM_SITE]
    if sem_site:
        texto = f"{len(sem_site)} dos {analisados} leads analisados não têm site próprio: público direto para venda de site."
        nicho = _mais_comum((l.get("nicho") or "").strip() for l in sem_site)
        if nicho and nicho[1] > 1:
            texto += f" O nicho que mais aparece é {nicho[0]} ({nicho[1]})."
        insights.append({"titulo": "Oportunidade", "texto": texto})

    prontos = [l for l in all_leads if l.get("_validado") and l.get("_whatsapp_compat") == "compativel"]
    if prontos:
        novos = sum(1 for l in prontos if l.get("status") in ("Novo", "Analisado"))
        texto = f"{len(prontos)} leads têm WhatsApp verificado."
        if novos:
            texto += f" {novos} ainda não receberam mensagem."
        insights.append({"titulo": "Abordagem", "texto": texto})

    aprovados = [l for l in all_leads if (l.get("_laudo") or {}).get("lead_aprovado_abordagem") == "sim"]
    cidade = _mais_comum((l.get("cidade") or "").strip() for l in aprovados)
    if cidade:
        insights.append({
            "titulo": "Cidade",
            "texto": f"{cidade[0]} concentra mais leads aprovados para abordagem ({cidade[1]} de {len(aprovados)}).",
        })

    pendentes = total - analisados
    if pendentes:
        insights.append({
            "titulo": "Próximo passo",
            "texto": f"{pendentes} leads ainda estão sem laudo. Valide-os para ampliar o funil.",
        })
    return insights


def leads_recentes(all_leads, limite=5):
    return sorted(all_leads, key=lambda l: (str(l.get("created_at") or ""), l.get("id") or 0), reverse=True)[:limite]


def _data_analise(lead):
    # analisado_em é gravado como "dd/mm/aaaa HH:MM"; converte para ordenar.
    try:
        data, hora = (lead.get("analisado_em") or "").split(" ")
        dia, mes, ano = data.split("/")
        return f"{ano}-{mes}-{dia} {hora}"
    except ValueError:
        return ""


def laudos_recentes(all_leads, limite=5):
    analisados = [l for l in all_leads if l.get("_validado")]
    return sorted(analisados, key=lambda l: (_data_analise(l), l.get("id") or 0), reverse=True)[:limite]


def get_filter_options():
    with get_connection() as connection:
        origens = [
            row["origem"]
            for row in connection.execute(
                """
                SELECT DISTINCT TRIM(origem_lead) AS origem FROM leads
                WHERE TRIM(COALESCE(origem_lead, '')) != ''
                ORDER BY origem
                """
            ).fetchall()
        ]
    return {
        "nichos": distinct_values("nicho"),
        "cidades": distinct_values("cidade"),
        "prioridades": distinct_values("prioridade"),
        "status": distinct_values("status"),
        "origens": origens,
    }


def lead_para_api(lead):
    return {key: value for key, value in lead.items() if key not in API_LEAD_EXCLUDE}


def get_leads_com_contagem(filters):
    """Leads filtrados + contagem por status do funil.

    A contagem ignora o filtro de status (respeita busca, nicho, cidade...),
    para que os chips mostrem quantos leads cada status teria.
    """
    sem_status = {**filters, "status": ""}
    base = get_leads_filtrados(sem_status)
    contagem = Counter(lead.get("status") or "" for lead in base)
    contagens = {status: contagem.get(status, 0) for status in STATUS_OPTIONS}
    contagens["_total"] = len(base)
    status = (filters.get("status") or "").strip()
    leads = [lead for lead in base if lead.get("status") == status] if status else base
    return leads, contagens


def _selo(nivel, rotulo, detalhe=""):
    return {"nivel": nivel, "rotulo": rotulo, "detalhe": detalhe or ""}


def montar_presenca(lead):
    """Selos de presença digital (good/warn/bad) com links, para o painel lateral."""
    laudo = lead.get("_laudo") or {}
    validado = lead.get("_validado")

    telefone = (lead.get("telefone_whatsapp") or "").strip()
    wa_link = whatsapp_link(telefone)
    compat = lead.get("_whatsapp_compat")
    if not telefone:
        whatsapp = _selo("bad", "Não informado")
    elif not validado:
        whatsapp = _selo("warn", "Não validado")
    elif compat == "compativel":
        whatsapp = _selo("good", "Verificado")
    elif compat == "divergente":
        whatsapp = _selo("bad", "Divergente")
    else:
        whatsapp = _selo("warn", "Incerto")
    whatsapp.update(valor=telefone, link=wa_link)
    whatsapp["detalhe"] = laudo.get("observacao_whatsapp") or ""

    insta_link = normalize_instagram(lead.get("instagram"))
    encontrado = lead.get("_instagram_encontrado")
    if validado and encontrado == "sim":
        instagram = _selo("good", "Encontrado")
    elif validado and encontrado == "nao" and not insta_link:
        instagram = _selo("bad", "Não encontrado")
    elif insta_link and not validado:
        instagram = _selo("warn", "Não validado")
    elif insta_link:
        instagram = _selo("warn", "Incerto")
    else:
        instagram = _selo("bad", "Não informado")
    instagram.update(valor=(lead.get("instagram") or "").strip(), link=insta_link)
    instagram["detalhe"] = laudo.get("instagram_observacao_oportunidade") or ""

    site_link = normalize_url(lead.get("site"))
    tipo = lead.get("_site_tipo")
    if validado and tipo in ("site_proprio", "proprio"):
        site = _selo("good", "Site próprio")
    elif validado and tipo in ("site_terceirizado", "cardapio_plataforma_externa", "generico"):
        site = _selo("warn", "Site terceirizado")
    elif validado and tipo in ("nao_encontrado", "rede_social"):
        site = _selo("bad", "Sem site próprio")
    elif site_link and not validado:
        site = _selo("warn", "Não validado")
    elif site_link:
        site = _selo("warn", "Incerto")
    else:
        site = _selo("bad", "Sem site")
    site.update(valor=(lead.get("site") or "").strip(), link=site_link)
    site["detalhe"] = laudo.get("motivo_qualidade_site") or lead.get("qualidade_site") or ""

    return {"whatsapp": whatsapp, "instagram": instagram, "site": site}


def montar_detalhe(lead):
    """Dados extras do painel: presença digital, fontes e mensagem de abordagem."""
    laudo = lead.get("_laudo") or {}
    try:
        fontes = json.loads(lead.get("ia_real_fontes") or "[]")
    except Exception:
        fontes = []
    fontes = [f for f in fontes if isinstance(f, str) and f.startswith(("http://", "https://"))]

    mensagem = laudo.get("mensagem_whatsapp") or lead.get("mensagem") or ""
    presenca = montar_presenca(lead)
    wa_link = presenca["whatsapp"]["link"]
    if wa_link and mensagem:
        wa_link = f"{wa_link}?text={quote(mensagem)}"
    return {
        "presenca": presenca,
        "fontes": fontes,
        "mensagem": mensagem,
        "whatsapp_abordagem": wa_link,
        "proximo_passo": laudo.get("proximo_passo") or "",
        "analisado_em": lead.get("analisado_em") or "",
    }


def get_funil(all_leads):
    """Quantidade de leads em cada status do funil, com percentual sobre o total."""
    contagem = Counter(lead.get("status") or "" for lead in all_leads)
    total = len(all_leads)
    return [
        {"status": status, "total": contagem.get(status, 0), "pct": percentual(contagem.get(status, 0), total)}
        for status in STATUS_OPTIONS
    ]


def proximos_para_abordar(all_leads, limite=5):
    """Leads aprovados pelo laudo que ainda não receberam mensagem, maior score primeiro."""
    prontos = [
        lead for lead in all_leads
        if lead.get("_status_geral") == "Aprovado" and lead.get("status") in ("Novo", "Analisado")
    ]
    return sorted(prontos, key=lambda l: (-l.get("_score", 0), l.get("id") or 0))[:limite]


def fatos_do_laudo(lead):
    """Fatos verificados no laudo, usados como badges e como base da mensagem (nada inventado)."""
    laudo = lead.get("_laudo") or {}
    fatos = []
    tipo = lead.get("_site_tipo")
    if tipo in SITE_TIPOS_SEM_SITE:
        fatos.append({"chave": "sem_site", "rotulo": "Sem site próprio", "nivel": "bad"})
    elif tipo in ("site_terceirizado", "cardapio_plataforma_externa", "generico"):
        fatos.append({"chave": "site_terceirizado", "rotulo": "Site terceirizado", "nivel": "warn"})
    elif tipo in ("site_proprio", "proprio"):
        fatos.append({"chave": "site_proprio", "rotulo": "Site próprio", "nivel": "good"})

    compat = lead.get("_whatsapp_compat")
    if compat == "compativel":
        fatos.append({"chave": "whatsapp_ok", "rotulo": "WhatsApp compatível", "nivel": "good"})
    elif compat == "divergente":
        fatos.append({"chave": "whatsapp_divergente", "rotulo": "WhatsApp divergente", "nivel": "bad"})
    else:
        fatos.append({"chave": "whatsapp_incerto", "rotulo": "WhatsApp incerto", "nivel": "warn"})

    if lead.get("_instagram_encontrado") == "sim":
        fatos.append({"chave": "instagram_ok", "rotulo": "Instagram encontrado", "nivel": "good"})
    elif lead.get("_instagram_encontrado") == "nao":
        fatos.append({"chave": "instagram_ausente", "rotulo": "Instagram não encontrado", "nivel": "bad"})

    if laudo.get("instagram_tipo_link_bio") == "linktree_ou_similar":
        fatos.append({"chave": "bio_agregador", "rotulo": "Bio com agregador de links", "nivel": "warn"})
    elif laudo.get("instagram_tipo_link_bio") == "whatsapp_direto":
        fatos.append({"chave": "bio_whatsapp", "rotulo": "Bio leva direto ao WhatsApp", "nivel": "warn"})
    return fatos


def fontes_de_captura():
    """Só informa se cada fonte está configurada; nunca devolve a chave."""
    google_places = bool(get_google_places_api_key())
    token_apify = os.getenv("APIFY_API_TOKEN", "").strip()
    return {
        "google_places": google_places,
        "apify": bool(token_apify) and token_apify != "sua_chave_aqui",
    }


def render_lead_row(lead):
    return render_template("partials/lead_rows.html", leads=[lead], status_options=STATUS_OPTIONS)


@app.route("/dashboard")
@app.route("/app")
@login_required
def dashboard():
    # Uma leitura só: métricas, cidades, insights e tabelas saem da mesma lista.
    all_leads = [processar_lead(row) for row in list_leads()]
    metrics = get_metrics(all_leads)
    return render_template(
        "index.html",
        active_page="dashboard",
        metrics=metrics,
        cidades=get_prioridade_por_cidade(all_leads),
        insights=gerar_insights(all_leads, metrics),
        funil=get_funil(all_leads),
        proximos=proximos_para_abordar(all_leads),
        status_options=STATUS_OPTIONS,
    )


@app.route("/index")
@login_required
def index():
    return redirect(url_for("dashboard"))


@app.route("/leads/novo", methods=["GET", "POST"])
@login_required
def new_lead():
    if request.method == "POST":
        payload = prepare_lead_payload(request.form)
        create_lead(payload)
        flash("Lead cadastrado e diagnosticado com sucesso.", "success")
        return redirect(url_for("leads_page"))

    return render_template(
        "form.html",
        lead=None,
        title="Novo lead",
        action=url_for("new_lead"),
        status_options=STATUS_OPTIONS,
        site_quality_options=SITE_QUALITY_OPTIONS,
        active_page="leads",
    )


@app.route("/capturar-leads")
@app.route("/buscar-leads")
@login_required
def buscar_leads():
    return render_template(
        "buscar_leads.html",
        active_page="capturar",
        fonte_configurada=fontes_de_captura()["google_places"],
    )


@app.route("/leads")
@login_required
def leads_page():
    filters = get_filters()
    leads, contagens = get_leads_com_contagem(filters)
    return render_template(
        "leads.html",
        active_page="leads",
        leads=leads,
        contagens=contagens,
        filtrado=has_active_filters(filters),
        filters=filters,
        filter_options=get_filter_options(),
        status_options=STATUS_OPTIONS,
    )


@app.route("/api/leads", methods=["GET"])
@login_required
def api_list_leads():
    filters = get_filters()
    leads, contagens = get_leads_com_contagem(filters)
    return jsonify(
        {
            "ok": True,
            "total": len(leads),
            "contagens": contagens,
            "leads": [lead_para_api(lead) for lead in leads],
            # Linhas já renderizadas pelo mesmo partial do leads.html (evita duplicar markup no JS).
            "html": render_template(
                "partials/lead_rows.html",
                leads=leads,
                status_options=STATUS_OPTIONS,
                filtrado=any((filters.get(k) or "").strip() for k in filters),
            ),
        }
    )


@app.route("/api/leads/<int:lead_id>", methods=["GET"])
@login_required
def api_get_lead(lead_id):
    row = get_lead(lead_id)
    if row is None:
        return jsonify({"ok": False, "message": "Lead não encontrado."}), 404
    lead = processar_lead(row)
    detalhe = montar_detalhe(lead)
    return jsonify(
        {
            "ok": True,
            "lead": lead_para_api(lead),
            "detalhe": detalhe,
            "drawer_html": render_template(
                "partials/lead_drawer.html", lead=lead, detalhe=detalhe, status_options=STATUS_OPTIONS
            ),
            "row_html": render_lead_row(lead),
        }
    )


@app.route("/laudos")
@login_required
def laudos_page():
    # Etapa 2.3: os laudos vivem no painel lateral do lead; a rota antiga leva aos aprovados.
    return redirect(url_for("leads_page", aprovacao="sim"))


@app.route("/mensagens")
@login_required
def mensagens_page():
    leads = get_leads_filtrados()
    com_laudo = [lead for lead in leads if lead.get("_validado")]
    aprovados = [lead for lead in com_laudo if lead.get("_status_geral") == "Aprovado"]
    aprovados.sort(key=lambda l: (-l.get("_score", 0), l.get("id") or 0))
    itens = [
        {
            "id": lead["id"],
            "nome": lead.get("nome_empresa") or "",
            "nicho": lead.get("nicho") or "",
            "cidade": lead.get("cidade") or "",
            "score": lead.get("_score", 0),
            "status": lead.get("status") or "",
            "whatsapp": whatsapp_link(lead.get("telefone_whatsapp")) or "",
            "fatos": fatos_do_laudo(lead),
        }
        for lead in aprovados
    ]
    return render_template(
        "mensagens.html",
        active_page="mensagens",
        leads=leads,
        itens=itens,
        total_com_laudo=len(com_laudo),
        total_aprovados=len(aprovados),
    )


@app.route("/oportunidades")
@login_required
def oportunidades_page():
    return redirect(url_for("leads_page"))


@app.route("/insights")
@login_required
def insights_page():
    # Etapa 2.3: os insights viraram um bloco da Visão geral.
    return redirect(url_for("dashboard"))


@app.route("/configuracoes")
@login_required
def configuracoes_page():
    usadas, limite = get_current_limit_info()
    return render_template(
        "configuracoes.html",
        active_page="configuracoes",
        fontes=fontes_de_captura(),
        analises={"usadas": usadas, "limite": limite, "pct": min(percentual(usadas, limite), 100)},
    )


@app.route("/importar-apify", methods=["GET", "POST"])
@login_required
def importar_apify():
    if request.method == "POST":
        csv_file = request.files.get("csv_file")
        if not csv_file or not csv_file.filename:
            flash("Escolha um arquivo CSV exportado do Apify.", "error")
            return redirect(url_for("importar_apify"))

        if not csv_file.filename.lower().endswith(".csv"):
            flash("Envie um arquivo com extensão .csv.", "error")
            return redirect(url_for("importar_apify"))

        summary = import_apify_csv(csv_file)
        flash(
            (
                f"Importação concluída: {summary['total_linhas']} linha(s) lida(s), "
                f"{summary['importados']} lead(s) importado(s), "
                f"{summary['duplicados']} duplicado(s) ignorado(s), "
                f"{summary['erros']} erro(s)."
            ),
            "success" if summary["erros"] == 0 else "error",
        )

        if summary["mensagens_erro"]:
            flash(" | ".join(summary["mensagens_erro"][:4]), "error")

        return redirect(url_for("leads_page"))

    return render_template("importar_apify.html", active_page="configuracoes")


@app.route("/api/apify/buscar", methods=["POST"])
@app.route("/api/google-places/buscar", methods=["POST"])
@login_required
def api_apify_buscar():
    data = request.get_json(silent=True) or request.form
    nicho = (data.get("nicho") or "").strip()
    cidade = (data.get("cidade") or "").strip()
    limite = normalize_limit(data.get("limite", 20))

    if not nicho or not cidade:
        return jsonify(
            {
                "ok": False,
                "message": "Informe nicho e cidade para buscar leads.",
                "leads": [],
            }
        ), 400

    result = search_google_places(nicho, cidade, limite)
    status_code = 200 if result["ok"] else 400
    return jsonify(result), status_code


@app.route("/api/apify/salvar", methods=["POST"])
@app.route("/api/google-places/salvar", methods=["POST"])
@login_required
def api_apify_salvar():
    data = request.get_json(silent=True) or {}
    lead = data.get("lead") or {}
    if not lead:
        return jsonify({"ok": False, "message": "Lead inválido para salvar."}), 400

    result = create_lead_if_not_duplicate(lead)
    if result["saved"]:
        return jsonify({"ok": True, "message": "Lead salvo no CRM.", "id": result["id"]})
    return jsonify({"ok": False, "message": "Lead já existe no CRM.", "reason": "duplicado"}), 409


@app.route("/api/apify/salvar-todos", methods=["POST"])
@app.route("/api/google-places/salvar-todos", methods=["POST"])
@login_required
def api_apify_salvar_todos():
    data = request.get_json(silent=True) or {}
    leads = data.get("leads") or []
    saved = 0
    duplicated = 0

    for lead in leads:
        result = create_lead_if_not_duplicate(lead)
        if result["saved"]:
            saved += 1
        else:
            duplicated += 1

    return jsonify(
        {
            "ok": True,
            "message": f"{saved} lead(s) salvo(s). {duplicated} duplicado(s) ignorado(s).",
            "saved": saved,
            "duplicated": duplicated,
        }
    )


@app.route("/leads/<int:lead_id>/editar", methods=["GET", "POST"])
@login_required
def edit_lead(lead_id):
    lead = get_lead(lead_id)
    if lead is None:
        flash("Lead não encontrado.", "error")
        return redirect(url_for("leads_page"))

    if request.method == "POST":
        payload = prepare_lead_payload(request.form)
        update_lead(lead_id, payload)
        flash("Lead atualizado com diagnóstico recalculado.", "success")
        return redirect(url_for("leads_page"))

    return render_template(
        "form.html",
        lead=lead,
        title="Editar lead",
        action=url_for("edit_lead", lead_id=lead_id),
        status_options=STATUS_OPTIONS,
        site_quality_options=SITE_QUALITY_OPTIONS,
        active_page="leads",
    )


@app.route("/leads/<int:lead_id>/excluir", methods=["POST"])
@login_required
def remove_lead(lead_id):
    delete_lead(lead_id)
    flash("Lead excluído.", "success")
    return redirect(url_for("leads_page"))


@app.route("/api/leads/<int:lead_id>/analisar", methods=["POST"])
@login_required
def api_analisar_lead(lead_id):
    lead = get_lead(lead_id)
    if not lead:
        return jsonify({"ok": False, "message": "Lead não encontrado."}), 404
        
    nicho = lead["nicho"] or "empresa"
    cidade = lead["cidade"] or "sua cidade"
    nome = lead["nome_empresa"] or "Empresa"
    qualidade = lead["qualidade_site"] or "Não tem site"
    
    # Generate simulated AI response based on real lead data
    if qualidade in ("Não tem site", "Só rede social"):
        potencial = "Alto"
        motivo = f"A {nome} não possui site próprio, dependendo inteiramente de terceiros ou sem presença online. Há alta demanda de clientes buscando por {nicho} em {cidade} no Google, representando perda de leads diários."
        sugestao = f"Olá, tudo bem? Vi o perfil da {nome} e notei que vocês atendem o nicho de {nicho} em {cidade}, mas ainda não possuem site. Desenvolvi um modelo de site sob medida para {nicho} que pode dobrar seus agendamentos/vendas. Posso te enviar para dar uma olhada sem compromisso?"
    elif qualidade in ("Site ruim", "Site mediano"):
        potencial = "Médio"
        motivo = f"A {nome} já possui site, porém identificamos lentidão no carregamento no celular e falta de botões de conversão direta via WhatsApp. Isso afasta cerca de 40% das visitas."
        sugestao = f"Olá! Notei que a {nome} tem um site ativo, mas identifiquei que ele demora cerca de 5 segundos para carregar no celular, o que faz vocês perderem clientes para a concorrência em {cidade}. Preparei um layout moderno de carregamento instantâneo. Quer ver uma prévia?"
    else:
        potencial = "Baixo"
        motivo = f"O site da {nome} está em bom estado. A oportunidade aqui é oferecer serviços de SEO local ou tráfego pago (Google Ads) para aumentar a visibilidade no nicho de {nicho} em {cidade}."
        sugestao = f"Olá! Parabéns pelo site da {nome}, está excelente! Sou especialista em SEO e tráfego pago em {cidade}. Notei que vocês poderiam estar no topo das buscas para '{nicho}'. Topa uma breve call para ver o potencial de crescimento?"
        
    # Save the analysis back to the database
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE leads
            SET ai_analisado = 1,
                ai_potencial = ?,
                ai_motivo = ?,
                ai_sugestao = ?,
                status = 'Analisado'
            WHERE id = ?
            """,
            (potencial, motivo, sugestao, lead_id)
        )
        
    return jsonify({
        "ok": True,
        "ai_potencial": potencial,
        "ai_motivo": motivo,
        "ai_sugestao": sugestao,
        "status": "Analisado"
    })


@app.route("/api/leads/<int:lead_id>/status", methods=["POST"])
@login_required
def api_update_status(lead_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if not new_status or new_status not in STATUS_OPTIONS:
        return jsonify({"ok": False, "message": "Status inválido."}), 400
        
    with get_connection() as connection:
        connection.execute(
            "UPDATE leads SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_status, lead_id)
        )

    # Devolve a linha atualizada para o front trocar só ela na tabela.
    row = get_lead(lead_id)
    if row is None:
        return jsonify({"ok": False, "message": "Lead não encontrado."}), 404
    lead = processar_lead(row)
    return jsonify({
        "ok": True,
        "message": "Status atualizado com sucesso.",
        "status": new_status,
        "lead": lead_para_api(lead),
        "html": render_lead_row(lead),
    })


@app.route("/api/leads/<int:lead_id>/pesquisar-ia-real", methods=["POST"])
@login_required
def api_pesquisar_ia_real_lead(lead_id):
    db_lead = get_lead(lead_id)
    if not db_lead:
        return jsonify({"ok": False, "message": "Lead não encontrado."}), 404
    lead = dict(db_lead)
        
    data = request.get_json(silent=True) or {}
    reanalisar = data.get("reanalisar") == True
    
    # Check if there is already a saved result and we are not forcing reanalysis
    if not reanalisar and lead.get("ia_real_resultado"):
        try:
            saved_data = json.loads(lead["ia_real_resultado"])
            fontes = []
            if lead.get("ia_real_fontes"):
                fontes = json.loads(lead["ia_real_fontes"])
            return jsonify({
                "ok": True,
                "cached": True,
                "data": saved_data,
                "score": lead.get("ia_real_score", 0),
                "potencial": lead.get("ia_real_potencial", "baixo"),
                "fontes": fontes,
                "analisado_em": lead.get("analisado_em")
            })
        except Exception:
            pass # fallback to query if json loading fails
            
    # Run the real AI analysis
    res = execute_real_ai_analysis(lead)
    if not res["ok"]:
        return jsonify({
            "ok": False,
            "message": res["message"],
            "connection_issue": bool(res.get("connection_issue"))
        }), 400
        
    result_data = res["data"]
    score = result_data.get("score", 0)
    potencial = result_data.get("potencial", "baixo")
    fontes = result_data.get("fontes", [])
    
    # Save results to database
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE leads
            SET ia_real_resultado = ?,
                ia_real_score = ?,
                ia_real_potencial = ?,
                ia_real_fontes = ?,
                analisado_em = strftime('%d/%m/%Y %H:%M', datetime('now', 'localtime')),
                status = 'Analisado'
            WHERE id = ?
            """,
            (
                json.dumps(result_data),
                score,
                potencial,
                json.dumps(fontes),
                lead_id
            )
        )
        
    # Get current limit count
    count, limit = get_current_limit_info()
    
    return jsonify({
        "ok": True,
        "cached": False,
        "data": result_data,
        "score": score,
        "potencial": potencial,
        "fontes": fontes,
        "limit_info": {
            "count": count,
            "limit": limit
        }
    })


@app.route("/api/apify/test-connection", methods=["POST"])
@login_required
def api_test_apify_connection():
    import os
    import urllib.request
    import urllib.parse
    import json
    from google_places import load_env_file
    load_env_file()
    
    token = os.getenv("APIFY_API_TOKEN", "").strip()
    if not token or token == "sua_chave_aqui":
        return jsonify({"ok": False, "message": "Token do Apify não configurado no .env."}), 400
        
    try:
        url = f"https://api.apify.com/v2/users/me?token={urllib.parse.quote(token)}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = response.read().decode("utf-8")
            user_info = json.loads(res_data)
            
        username = user_info.get("data", {}).get("username", "usuário")
        email = user_info.get("data", {}).get("email", "")
        return jsonify({
            "ok": True,
            "message": f"Conexão com Apify estabelecida com sucesso! Usuário: {username} ({email})"
        })
    except urllib.error.HTTPError as he:
        if he.code == 401:
            return jsonify({"ok": False, "message": "Token do Apify inválido ou expirado."}), 401
        return jsonify({"ok": False, "message": f"Erro de API do Apify (HTTP {he.code}): {he.reason}"}), 400
    except Exception as e:
        return jsonify({"ok": False, "message": f"Erro inesperado ao conectar com Apify: {str(e)}"}), 500


@app.errorhandler(500)
def erro_interno(error):
    # O Flask já registra o traceback completo no terminal ("Exception on ... [GET]")
    # antes de chamar este handler; aqui só marcamos a rota e mostramos a página amigável.
    original = getattr(error, "original_exception", None)
    app.logger.error(
        "Erro 500 em %s %s: %s (traceback completo acima)",
        request.method,
        request.path,
        f"{type(original).__name__}: {original}" if original else error,
    )
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "message": "Erro interno no servidor. Tente novamente."}), 500
    try:
        return render_template("errors/500.html"), 500
    except Exception:
        # Se até a página de erro falhar, devolve HTML mínimo.
        return "<h1>Erro interno</h1><p>Tente recarregar a página.</p>", 500


# Iniciar DB na carga do modulo para garantir tabelas.
# Em produção, não derruba o processo inteiro se houver falha:
# expõe o motivo em /health para diagnóstico.
try:
    init_db()
    app.config["DB_INIT_ERROR"] = None
except Exception as exc:
    app.config["DB_INIT_ERROR"] = f"{type(exc).__name__}: {exc}"
    print("ERRO AO INICIAR BANCO:", app.config["DB_INIT_ERROR"])
    print(traceback.format_exc())

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
