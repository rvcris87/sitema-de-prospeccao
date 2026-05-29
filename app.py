import os
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for, session
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

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
from google_places import normalize_limit, search_google_places
from functools import wraps
import json
from ia_real_service import execute_real_ai_analysis, get_current_limit_info

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
        "current_user": current_user,
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
    return {"ok": True, "service": "sitema-de-prospeccao"}, 200


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
    session["user_plan"] = "Plano Elite"
    flash("Acesso de demonstração ativado!", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Sessão encerrada com sucesso.", "success")
    return redirect(url_for("landing"))


def build_dashboard_context():
    filters = {
        "nicho": request.args.get("nicho", ""),
        "cidade": request.args.get("cidade", ""),
        "prioridade": request.args.get("prioridade", ""),
        "status": request.args.get("status", ""),
        "site_filter": request.args.get("site_filter", ""),
        "tipo_site": request.args.get("tipo_site", ""),
        "whatsapp_compat": request.args.get("whatsapp_compat", ""),
        "instagram_encontrado": request.args.get("instagram_encontrado", ""),
        "origem_lead": request.args.get("origem_lead", ""),
        "data_referencia": request.args.get("data_referencia", ""),
    }
    raw_leads = [dict(row) for row in list_leads(filters)]
    leads = []

    for lead in raw_leads:
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
        leads.append(lead)

    def passes_advanced_filters(lead):
        if filters["tipo_site"] and lead.get("_site_tipo") != filters["tipo_site"]:
            return False
        if filters["whatsapp_compat"] and lead.get("_whatsapp_compat") != filters["whatsapp_compat"]:
            return False
        if filters["instagram_encontrado"] and lead.get("_instagram_encontrado") != filters["instagram_encontrado"]:
            return False
        if filters["origem_lead"] and (lead.get("origem_lead") or "").strip() != filters["origem_lead"]:
            return False
        if filters["data_referencia"]:
            created_at = str(lead.get("created_at") or "")
            if not created_at.startswith(filters["data_referencia"]):
                return False
        return True

    leads = [lead for lead in leads if passes_advanced_filters(lead)]

    # Calculate metrics focused on lead quality verification
    all_leads = [dict(row) for row in list_leads()]
    leads_importados = len(all_leads)
    leads_validados = sum(1 for l in all_leads if l.get("ia_real_resultado"))
    whatsapps_compativeis = 0
    whatsapps_incerto_suspeitos = 0
    leads_descartados = 0
    leads_com_ressalvas = 0
    sites_terceirizados = 0
    oportunidades_altas = 0
    leads_aprovados = 0
    mensagens_enviadas = sum(1 for l in all_leads if l.get("status") == "Mensagem enviada")
    respostas_recebidas = sum(1 for l in all_leads if l.get("status") == "Respondeu")
    empresas_sem_site = sum(1 for l in all_leads if l.get("qualidade_site") in ("Não tem site", "Só rede social"))

    for lead in all_leads:
        raw = lead.get("ia_real_resultado")
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if data.get("compatibilidade_whatsapp") == "compativel":
            whatsapps_compativeis += 1
        if data.get("compatibilidade_whatsapp") in ("incerto", "divergente"):
            whatsapps_incerto_suspeitos += 1
        if data.get("lead_aprovado_abordagem") == "com_ressalvas":
            leads_com_ressalvas += 1
        if data.get("lead_aprovado_abordagem") == "nao":
            leads_descartados += 1
        if data.get("tipo_site") in ("site_terceirizado", "cardapio_plataforma_externa"):
            sites_terceirizados += 1
        if data.get("lead_aprovado_abordagem") == "sim":
            leads_aprovados += 1
        if data.get("prioridade") == "alta":
            oportunidades_altas += 1
    
    metrics = {
        "leads_importados": leads_importados,
        "leads_validados": leads_validados,
        "leads_aprovados": leads_aprovados,
        "leads_descartados": leads_descartados,
        "whatsapps_compativeis": whatsapps_compativeis,
        "whatsapps_incerto_suspeitos": whatsapps_incerto_suspeitos,
        "sem_site": empresas_sem_site,
        "oportunidades_altas": oportunidades_altas,
        "mensagens_enviadas": mensagens_enviadas,
        "respostas_recebidas": respostas_recebidas,
        "leads_com_ressalvas": leads_com_ressalvas,
        "sites_terceirizados": sites_terceirizados,
    }
    
    filter_options = {
        "nichos": distinct_values("nicho"),
        "cidades": distinct_values("cidade"),
        "prioridades": distinct_values("prioridade"),
        "status": distinct_values("status"),
    }
    filter_options["origens"] = sorted(
        {
            (lead.get("origem_lead") or "").strip()
            for lead in all_leads
            if (lead.get("origem_lead") or "").strip()
        }
    )
    return {
        "leads": leads,
        "filters": filters,
        "filter_options": filter_options,
        "status_options": STATUS_OPTIONS,
        "site_quality_options": SITE_QUALITY_OPTIONS,
        "metrics": metrics,
    }


@app.route("/dashboard")
@app.route("/app")
@login_required
def dashboard():
    context = build_dashboard_context()
    return render_template("index.html", active_page="dashboard", **context)


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
    return render_template("buscar_leads.html", active_page="capturar")


@app.route("/leads")
@login_required
def leads_page():
    context = build_dashboard_context()
    return render_template("leads.html", active_page="leads", **context)


@app.route("/laudos")
@login_required
def laudos_page():
    context = build_dashboard_context()
    return render_template("laudos.html", active_page="laudos", **context)


@app.route("/mensagens")
@login_required
def mensagens_page():
    context = build_dashboard_context()
    return render_template("mensagens.html", active_page="mensagens", **context)


@app.route("/oportunidades")
@login_required
def oportunidades_page():
    context = build_dashboard_context()
    return render_template("oportunidades.html", active_page="oportunidades", **context)


@app.route("/insights")
@login_required
def insights_page():
    context = build_dashboard_context()
    return render_template("insights.html", active_page="insights", **context)


@app.route("/configuracoes")
@login_required
def configuracoes_page():
    context = build_dashboard_context()
    return render_template("configuracoes.html", active_page="configuracoes", **context)


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
        
    return jsonify({"ok": True, "message": "Status atualizado com sucesso.", "status": new_status})


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


# Iniciar DB na carga do modulo para garantir tabelas
init_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
