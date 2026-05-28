import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "leads.db"

def seed():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Update statuses to match new options
    cursor.execute("UPDATE leads SET status = 'Analisado' WHERE status = 'Verificado'")
    cursor.execute("UPDATE leads SET status = 'Recusado' WHERE status = 'Sem interesse'")
    conn.commit()
    print("Updated existing statuses.")

    # 2. Get some leads to enrich with AI analyses
    leads = cursor.execute("SELECT * FROM leads LIMIT 15").fetchall()
    
    # We will enrich them with simulated AI analyses
    for lead in leads:
        lead_id = lead["id"]
        nicho = lead["nicho"] or "empresa"
        cidade = lead["cidade"] or "sua cidade"
        nome = lead["nome_empresa"] or "Empresa"
        qualidade = lead["qualidade_site"] or "Não tem site"
        
        # Determine AI potential and reason based on lead data
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

        cursor.execute(
            """
            UPDATE leads
            SET ai_analisado = 1,
                ai_potencial = ?,
                ai_motivo = ?,
                ai_sugestao = ?
            WHERE id = ?
            """,
            (potencial, motivo, sugestao, lead_id)
        )
    
    conn.commit()
    print("Seeded AI analysis data for 15 leads.")
    
    # 3. Check if table is empty (just in case they start with an empty DB, let's insert a couple of robust ones)
    count = cursor.execute("SELECT count(*) FROM leads").fetchone()[0]
    if count == 0:
        print("Database empty. Seeding mock leads...")
        mock_leads = [
            ("Barbearia Rota 66", "Barbearia", "Curitiba", "41999991111", "@barbearia_rota66", "", "Só rede social", "Novo", "Alta", "Alta prioridade: empresa sem site próprio e com canal direto para abordagem."),
            ("Clínica Odonto Riso", "Dentista", "São Paulo", "11988882222", "@odontoriso_sp", "", "Não tem site", "Novo", "Alta", "Alta prioridade: empresa sem site e com telefone disponível."),
            ("Cantina Bella Italia", "Restaurante", "Florianópolis", "48966664444", "@bellaitalia_floripa", "www.bellaitalia.com.br", "Site ruim", "Analisado", "Média", "Média prioridade: já existe um site, mas há espaço para melhorar a presença digital."),
            ("Academia Fit Life", "Academia", "Belo Horizonte", "31977773333", "@fitlife_bh", "www.fitlifebh.com.br", "Site bom", "Novo", "Baixa", "Baixa prioridade: a empresa já possui site e pode ser avaliada depois."),
            ("Mecânica Auto Car", "Oficina Mecânica", "São Paulo", "11944446666", "", "", "Não tem site", "Mensagem enviada", "Alta", "Alta prioridade: empresa sem site próprio."),
        ]
        for nome, nicho, cidade, whatsapp, insta, site, qualidade, status, prioridade, diag in mock_leads:
            cursor.execute(
                """
                INSERT INTO leads (nome_empresa, nicho, cidade, telefone_whatsapp, instagram, site, qualidade_site, status, prioridade, diagnostico, mensagem, ai_analisado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 0)
                """,
                (nome, nicho, cidade, whatsapp, insta, site, qualidade, status, prioridade, diag)
            )
        conn.commit()
        print("Inserted mock leads since DB was empty.")

    conn.close()

if __name__ == "__main__":
    seed()
