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
Você é um consultor comercial de alta performance especializado em venda de websites para empresas locais.
Sua tarefa é analisar os resultados de pesquisa na web para uma determinada empresa local e preencher um relatório de diagnóstico no formato JSON especificado.

IMPORTANTE:
- Responda EXCLUSIVAMENTE em formato JSON válido. Não inclua qualquer texto explicativo fora do bloco JSON.
- Não invente informações. Se não encontrar evidências da empresa ou de seu site, use "incerto" ou "nao_encontrado" nos campos correspondentes.
- A mensagem de WhatsApp deve ser amigável, iniciar uma conversa de forma natural, focar no principal problema comercial encontrado e sugerir uma melhoria sem parecer spam ou texto automático. Use "você".

O esquema do JSON de resposta deve ser exatamente:
{
  "empresa_existe": "sim" | "nao" | "incerto",
  "site_encontrado": "sim" | "nao" | "incerto",
  "tipo_site": "proprio" | "generico" | "rede_social" | "nao_encontrado" | "incerto",
  "presenca_digital": "fraca" | "media" | "boa" | "incerta",
  "potencial": "baixo" | "medio" | "alto",
  "score": 0-100 (número representando urgência e oportunidade de venda de site, onde 100 é máxima urgência/oportunidade),
  "diagnostico": "diagnóstico comercial muito curto e objetivo (máximo 2 frases)",
  "problema_detectado": "principal falha ou problema detectado (ex: site lento, sem site próprio, link quebrado, ausência de botão para whatsapp)",
  "oferta_recomendada": "site institucional, landing page de alta conversão, página de agendamento, cardápio online ou vitrine digital",
  "preco_sugerido": "ex: R$ 1.500 a R$ 2.500",
  "mensagem_whatsapp": "mensagem curta, personalizada e persuasiva para envio no whatsapp iniciando a conversa sem parecer robô",
  "fontes": ["lista de links ou nomes de fontes encontradas nos resultados da pesquisa"]
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

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }
    
    try:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=25) as response:
            res_data = response.read().decode("utf-8")
            openai_res = json.loads(res_data)
            
        content_str = openai_res["choices"][0]["message"]["content"].strip()
        analysis_data = json.loads(content_str)
        
        # Merge search sources if not returned by OpenAI
        if not analysis_data.get("fontes") and sources:
            analysis_data["fontes"] = sources[:3]
            
        return {
            "ok": True,
            "data": analysis_data
        }
    except urllib.error.HTTPError as he:
        try:
            error_details = json.loads(he.read().decode("utf-8"))
            err_msg = error_details.get("error", {}).get("message", str(he))
        except Exception:
            err_msg = str(he)
        return {
            "ok": False,
            "message": f"Erro na API da OpenAI: {err_msg}"
        }
    except Exception as e:
        return {
            "ok": False,
            "message": f"Erro inesperado no processamento: {str(e)}"
        }
