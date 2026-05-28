import os
import re
import json
import urllib.request
import urllib.parse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
CONFIG_FILE = BASE_DIR / "ia_real_config.json"

def load_env_file():
    """Load env variables from .env if present."""
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        clean_line = line.strip()
        if not clean_line or clean_line.startswith("#") or "=" not in clean_line:
            continue
        key, value = clean_line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

def get_openai_api_key():
    load_env_file()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or key == "sua_chave_aqui":
        return None
    return key

def use_stored_prompt():
    raw_value = (os.getenv("OPENAI_USE_STORED_PROMPT", "false") or "").strip().lower()
    return raw_value in ("1", "true", "yes", "on")

# -------------------------------------------------------------
# Web Search Utility (DuckDuckGo HTML Parser)
# -------------------------------------------------------------
def search_duckduckgo(query):
    """Perform a free web search on DuckDuckGo and parse titles, snippets, and links."""
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8')
        
        snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        titles_links = re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)
        
        results = []
        clean_re = re.compile('<.*?>')
        
        for i in range(min(4, len(snippets))):
            snippet = clean_re.sub('', snippets[i]).strip()
            
            if i < len(titles_links):
                href, title_html = titles_links[i]
                title = clean_re.sub('', title_html).strip()
                # Clean DuckDuckGo redirection wrapper
                if "uddg=" in href:
                    try:
                        href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                    except Exception:
                        pass
            else:
                title = "No Title"
                href = ""
                
            results.append({
                "title": title,
                "snippet": snippet,
                "url": href
            })
        return results
    except Exception:
        return []

# -------------------------------------------------------------
# Demo limit manager
# -------------------------------------------------------------
def check_and_increment_limit():
    """Ensure the total number of real AI requests does not exceed 20."""
    limit = 20
    count = 0
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                count = data.get("total_analyses_run", 0)
                limit = data.get("max_limit", 20)
        except Exception:
            pass
            
    if count >= limit:
        return False, count, limit
        
    count += 1
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"total_analyses_run": count, "max_limit": limit}, f)
    except Exception:
        pass
        
    return True, count, limit

def get_current_limit_info():
    limit = 20
    count = 0
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                count = data.get("total_analyses_run", 0)
                limit = data.get("max_limit", 20)
        except Exception:
            pass
    return count, limit

# -------------------------------------------------------------
# Real AI Analysis Request
# -------------------------------------------------------------
def execute_real_ai_analysis(lead):
    """Search DDG for lead info, request analysis from OpenAI, and parse structured output."""
    api_key = get_openai_api_key()
    if not api_key:
        return {
            "ok": False,
            "message": "API de IA não configurada. Defina OPENAI_API_KEY no ambiente."
        }
        
    # Check limit
    allowed, count, limit = check_and_increment_limit()
    if not allowed:
        return {
            "ok": False,
            "message": "Limite de análises reais da demonstração atingido."
        }
        
    nome = lead.get("nome_empresa") or ""
    cidade = lead.get("cidade") or ""
    nicho = lead.get("nicho") or ""
    site = lead.get("site") or ""
    instagram = lead.get("instagram") or ""
    telefone = lead.get("telefone_whatsapp") or ""
    
    # 1. Perform web search
    search_query = f"{nome} {cidade} {nicho}"
    search_results = search_duckduckgo(search_query)
    
    formatted_results = ""
    sources = []
    if search_results:
        for idx, res in enumerate(search_results):
            formatted_results += f"[{idx+1}] {res['title']}\nLink: {res['url']}\nResumo: {res['snippet']}\n\n"
            if res['url']:
                sources.append(res['url'])
    else:
        formatted_results = "Nenhum resultado de pesquisa encontrado para a empresa local."
        
    # 2. Call OpenAI API
    system_prompt = """
Você é o verificador de qualidade de lead do Radar Local IA.
Sua tarefa é analisar apenas os sinais públicos fornecidos e montar um laudo técnico de confiabilidade do lead.

IMPORTANTE:
- Responda EXCLUSIVAMENTE em JSON válido.
- Não invente dados. Se faltar evidência, use "incerto".
- Não afirme posse do número com certeza absoluta; use "compatível", "divergente" ou "incerto".
- Seja objetivo e curto.

Retorne exatamente este formato:
{
  "empresa_existe": "sim" | "nao" | "incerto",
  "sinais_atividade": "alto" | "medio" | "baixo" | "incerto",
  "status_provavel": "ativa" | "incerta" | "possivel_inativa",
  "confianca_verificacao": 0-100,
  "whatsapp_numero_informado": "texto",
  "whatsapp_numero_instagram": "texto",
  "whatsapp_numero_site": "texto",
  "whatsapp_numero_wa_me": "texto",
  "compatibilidade_whatsapp": "compativel" | "divergente" | "incerto",
  "confianca_whatsapp": "alta" | "media" | "baixa",
  "observacao_whatsapp": "explicacao objetiva",
  "instagram_encontrado": "sim" | "nao" | "incerto",
  "instagram_bio_tem_link": "sim" | "nao" | "incerto",
  "instagram_tipo_link_bio": "dominio_proprio" | "linktree_ou_similar" | "whatsapp_direto" | "google_sites" | "canva_site" | "wix_ou_similar" | "cardapio_online_terceirizado" | "nao_identificado",
  "instagram_observacao_oportunidade": "texto curto",
  "site_encontrado": "sim" | "nao" | "incerto",
  "tipo_site": "site_proprio" | "site_terceirizado" | "rede_social" | "cardapio_plataforma_externa" | "nao_encontrado" | "incerto",
  "qualidade_site": "boa" | "media" | "fraca" | "ausente" | "incerta",
  "motivo_qualidade_site": "texto curto",
  "lead_aprovado_abordagem": "sim" | "nao" | "com_ressalvas",
  "prioridade": "baixa" | "media" | "alta",
  "score": 0-100,
  "motivo_prioridade": "texto curto",
  "potencial": "baixo" | "medio" | "alto",
  "diagnostico": "resumo curto do laudo",
  "problema_detectado": "principal risco ou falha detectada",
  "oferta_recomendada": "oferta indicada",
  "preco_sugerido": "faixa estimada",
  "mensagem_whatsapp": "mensagem curta de abordagem",
  "proximo_passo": "passo objetivo",
  "fontes": ["lista de links/fontes públicas usadas"]
}
"""

    user_content = f"""
Dados fornecidos pelo CRM:
- Nome da Empresa: {nome}
- Nicho: {nicho}
- Cidade: {cidade}
- Site registrado: {site}
- Instagram registrado: {instagram}
- Telefone registrado: {telefone}

Resultados da pesquisa na Web (DuckDuckGo):
{formatted_results}

Por favor, faça a análise com base estritamente nos resultados de busca fornecidos. Retorne apenas o JSON correspondente.
"""

    def build_default_analysis_payload():
        return {
            "empresa_existe": "",
            "sinais_atividade": "",
            "status_provavel": "",
            "confianca_verificacao": 0,
            "whatsapp_numero_informado": "",
            "whatsapp_numero_instagram": "",
            "whatsapp_numero_site": "",
            "whatsapp_numero_wa_me": "",
            "compatibilidade_whatsapp": "",
            "confianca_whatsapp": "",
            "observacao_whatsapp": "",
            "instagram_encontrado": "",
            "instagram_bio_tem_link": "",
            "instagram_tipo_link_bio": "",
            "instagram_observacao_oportunidade": "",
            "site_encontrado": "",
            "tipo_site": "",
            "qualidade_site": "",
            "motivo_qualidade_site": "",
            "presenca_digital": "",
            "lead_aprovado_abordagem": "",
            "prioridade": "",
            "potencial": "",
            "score": 0,
            "motivo_prioridade": "",
            "diagnostico": "",
            "problema_detectado": "",
            "oferta_recomendada": "",
            "preco_sugerido": "",
            "mensagem_whatsapp": "",
            "proximo_passo": "",
            "fontes": []
        }

    def coerce_analysis_payload(data):
        payload = build_default_analysis_payload()
        if isinstance(data, dict):
            payload.update(data)
        if not isinstance(payload.get("fontes"), list):
            payload["fontes"] = []
        try:
            payload["score"] = int(payload.get("score", 0) or 0)
        except Exception:
            payload["score"] = 0
        try:
            payload["confianca_verificacao"] = int(payload.get("confianca_verificacao", 0) or 0)
        except Exception:
            payload["confianca_verificacao"] = 0
        return payload

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        prompt_id = "pmpt_6a17c2a9df788193aad2e365367eff020ad4c95ecb1cc77f"
        prompt_version = "2"
        variables = {
            "nome_empresa": lead.get("nome") or lead.get("nome_empresa") or "",
            "cidade": lead.get("cidade") or "",
            "nicho": lead.get("nicho") or "",
            "site": lead.get("site") or "não informado",
            "instagram": lead.get("instagram") or "não informado",
            "telefone": lead.get("telefone") or lead.get("telefone_whatsapp") or "não informado"
        }
        
        # Log before the call
        print("--------------------------------------------------", flush=True)
        print("[OPENAI CALL] Iniciando chamada de IA", flush=True)
        print(f"Lead analisado: {nome or 'sem nome'}", flush=True)
        print(f"Prompt ID: {prompt_id}", flush=True)
        print(f"Prompt Version: {prompt_version}", flush=True)
        print(f"Variáveis enviadas: {json.dumps(variables, indent=2, ensure_ascii=False)}", flush=True)
        print(f"OPENAI_USE_STORED_PROMPT: {use_stored_prompt()}", flush=True)
        print("--------------------------------------------------", flush=True)

        content_str = ""
        if use_stored_prompt():
            try:
                response = client.responses.create(
                    prompt={
                        "id": prompt_id,
                        "version": prompt_version,
                        "variables": variables
                    }
                )
                content_str = (response.output_text or "").strip()
                print("[OPENAI SUCCESS] Chamada do Stored Prompt executada com sucesso.", flush=True)
            except Exception as stored_prompt_err:
                # Log the complete error if Stored Prompt call fails
                print("--------------------------------------------------", flush=True)
                print("[OPENAI ERROR] Falha completa na chamada com Stored Prompt:", flush=True)
                import traceback
                traceback.print_exc()
                print("--------------------------------------------------", flush=True)

                err_msg = str(stored_prompt_err or "").lower()
                variable_error = (
                    "unknown prompt variables" in err_msg
                    or "prompt variables" in err_msg
                    or "variable" in err_msg
                )

                if variable_error:
                    print("[FALLBACK] Erro de variável no Stored Prompt detectado. Executando fallback com input direto em responses.create().", flush=True)
                else:
                    print("[FALLBACK] Stored Prompt falhou por outro motivo. Executando fallback com input direto em responses.create().", flush=True)
        else:
            print("[OPENAI MODE] Stored Prompt desativado por configuração. Usando input direto.", flush=True)

        if not content_str:
            fallback_response = client.responses.create(
                model="gpt-4o-mini",
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                text={
                    "format": {
                        "type": "json_object"
                    }
                },
                temperature=0.2
            )
            content_str = (fallback_response.output_text or "").strip()
            print("[FALLBACK SUCCESS] Chamada direta executada com sucesso.", flush=True)
        
        try:
            analysis_data = json.loads(content_str)
        except Exception as parse_err:
            print(f"[ERROR] Erro ao parsear JSON retornado pela OpenAI: {parse_err}")
            print(f"[RAW OUTPUT] {content_str}")
            return {
                "ok": False,
                "message": "Erro ao processar o diagnóstico gerado pela inteligência artificial. O formato retornado é inválido."
            }

        analysis_data = coerce_analysis_payload(analysis_data)
        
        # Merge search sources if not returned by OpenAI
        if not analysis_data.get("fontes") and sources:
            analysis_data["fontes"] = sources[:3]
            
        return {
            "ok": True,
            "data": analysis_data
        }
    except Exception as e:
        print(f"[CRITICAL ERROR] Erro crítico no serviço de IA: {str(e)}")
        return {
            "ok": False,
            "message": f"Erro inesperado no serviço de IA: {str(e)}"
        }
