import os
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for, session
from werkzeug.middleware.proxy_fix import ProxyFix

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
    return {
        "normalize_url": normalize_url,
        "normalize_instagram": normalize_instagram,
        "only_digits": only_digits,
        "whatsapp_link": whatsapp_link,
    }


@app.route("/")
def landing():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    return render_template("landing.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("index"))
        
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        
        if email == "demo@radarlocal.com" and password == "123456":
            session["logged_in"] = True
            session["user_email"] = email
            flash("Login realizado com sucesso! Bem-vindo ao painel.", "success")
            return redirect(url_for("index"))
        else:
            flash("Credenciais inválidas. Use o acesso demo para testar.", "error")
            
    return render_template("login.html")


@app.route("/demo-login")
def demo_login():
    session["logged_in"] = True
    session["user_email"] = "demo@radarlocal.com"
    flash("Acesso de demonstração ativado!", "success")
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Sessão encerrada com sucesso.", "success")
    return redirect(url_for("landing"))


@app.route("/dashboard")
@login_required
def index():
    filters = {
        "nicho": request.args.get("nicho", ""),
        "cidade": request.args.get("cidade", ""),
        "prioridade": request.args.get("prioridade", ""),
        "status": request.args.get("status", ""),
        "site_filter": request.args.get("site_filter", ""),
    }
    leads = list_leads(filters)
    
    # Calculate metrics based on ALL leads
    all_leads = [dict(row) for row in list_leads()]
    total_leads = len(all_leads)
    leads_analisados = sum(1 for l in all_leads if l.get("ai_analisado") == 1 or l.get("status") != "Novo")
    alto_potencial = sum(1 for l in all_leads if l.get("prioridade") == "Alta")
    empresas_sem_site = sum(1 for l in all_leads if l.get("qualidade_site") in ("Não tem site", "Só rede social"))
    mensagens_enviadas = sum(1 for l in all_leads if l.get("status") == "Mensagem enviada")
    respostas_recebidas = sum(1 for l in all_leads if l.get("status") == "Respondeu")
    
    metrics = {
        "total": total_leads,
        "analisados": leads_analisados,
        "alto_potencial": alto_potencial,
        "sem_site": empresas_sem_site,
        "mensagens_enviadas": mensagens_enviadas,
        "respostas_recebidas": respostas_recebidas,
    }
    
    filter_options = {
        "nichos": distinct_values("nicho"),
        "cidades": distinct_values("cidade"),
        "prioridades": distinct_values("prioridade"),
        "status": distinct_values("status"),
    }
    return render_template(
        "index.html",
        leads=leads,
        filters=filters,
        filter_options=filter_options,
        status_options=STATUS_OPTIONS,
        site_quality_options=SITE_QUALITY_OPTIONS,
        metrics=metrics,
    )


@app.route("/leads/novo", methods=["GET", "POST"])
@login_required
def new_lead():
    if request.method == "POST":
        payload = prepare_lead_payload(request.form)
        create_lead(payload)
        flash("Lead cadastrado e diagnosticado com sucesso.", "success")
        return redirect(url_for("index"))

    return render_template(
        "form.html",
        lead=None,
        title="Novo lead",
        action=url_for("new_lead"),
        status_options=STATUS_OPTIONS,
        site_quality_options=SITE_QUALITY_OPTIONS,
    )


@app.route("/buscar-leads")
@login_required
def buscar_leads():
    return render_template("buscar_leads.html")


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

        return redirect(url_for("index"))

    return render_template("importar_apify.html")


@app.route("/api/google-places/buscar", methods=["POST"])
@login_required
def api_google_places_buscar():
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


@app.route("/api/google-places/salvar", methods=["POST"])
@login_required
def api_google_places_salvar():
    data = request.get_json(silent=True) or {}
    lead = data.get("lead") or {}
    if not lead:
        return jsonify({"ok": False, "message": "Lead inválido para salvar."}), 400

    result = create_lead_if_not_duplicate(lead)
    if result["saved"]:
        return jsonify({"ok": True, "message": "Lead salvo no CRM.", "id": result["id"]})
    return jsonify({"ok": False, "message": "Lead já existe no CRM.", "reason": "duplicado"}), 409


@app.route("/api/google-places/salvar-todos", methods=["POST"])
@login_required
def api_google_places_salvar_todos():
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
        return redirect(url_for("index"))

    if request.method == "POST":
        payload = prepare_lead_payload(request.form)
        update_lead(lead_id, payload)
        flash("Lead atualizado com diagnóstico recalculado.", "success")
        return redirect(url_for("index"))

    return render_template(
        "form.html",
        lead=lead,
        title="Editar lead",
        action=url_for("edit_lead", lead_id=lead_id),
        status_options=STATUS_OPTIONS,
        site_quality_options=SITE_QUALITY_OPTIONS,
    )


@app.route("/leads/<int:lead_id>/excluir", methods=["POST"])
@login_required
def remove_lead(lead_id):
    delete_lead(lead_id)
    flash("Lead excluído.", "success")
    return redirect(url_for("index"))


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
        return jsonify({"ok": False, "message": res["message"]}), 400
        
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
