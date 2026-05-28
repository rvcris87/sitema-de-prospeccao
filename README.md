# Prospecta Sites

Sistema web simples para prospecção de clientes locais para venda de sites.

## Stack

- Frontend: HTML, CSS e JavaScript
- Backend: Python Flask
- Banco: SQLite
- Estrutura: `app.py`, `database.py`, `templates/` e `static/`

## Como rodar

```bash
pip install flask
python app.py
```

Acesse `http://127.0.0.1:5000`.

## Google Places API

Crie um arquivo `.env` na raiz do projeto:

```bash
GOOGLE_PLACES_API_KEY=sua_chave_aqui
```

Depois acesse `http://127.0.0.1:5000/buscar-leads`.

O arquivo `google_places.py` concentra a integração. Nele você pode:

- Alterar `GOOGLE_PLACES_FIELD_MASK` para mudar os campos retornados pela API.
- Alterar `normalize_limit(..., maximum=20)` para permitir mais resultados.
- Ajustar `place_to_lead()` para transformar os dados do Google em campos do CRM.

## Funcionalidades

- Cadastro, edição e exclusão de leads.
- Diagnóstico automático de prioridade.
- Campo de qualidade do site.
- Mensagem personalizada para WhatsApp ou Instagram.
- Filtros por nicho, cidade, prioridade, status e presença de site.
- Botões para copiar mensagem, abrir WhatsApp, Instagram e site.
- Busca automática de empresas reais pela Google Places API.
- Salvamento individual ou em lote, ignorando duplicados por nome+cidade, telefone ou site.
- Importação de CSV do Apify Google Maps Scraper com diagnóstico e resumo da importação.

## Regras de diagnóstico

- Alta prioridade: sem site e com WhatsApp ou Instagram.
- Média prioridade: site ruim ou site mediano.
- Baixa prioridade: site bom.

## Integrações futuras

O projeto está preparado para ganhar módulos de integração com:

- Google Places API para descoberta automática de empresas locais.
- Apify para coleta de dados públicos.
- n8n para automações de prospecção e follow-up.
- Google Sheets para sincronização com planilhas.
