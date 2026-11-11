# OpenAI: diagnóstico de ambiente e operação

## Status atual

- A integração existente está correta e continua lendo `OPENAI_API_KEY` por variável de ambiente.
- A chave foi identificada e o SDK `openai` está disponível.
- O erro observado localmente não é de código nem de chave: é bloqueio de rede/ambiente (`WinError 10013` / falha de socket).

## Comportamento aplicado no app

- Se houver falha de conexão com OpenAI (`Connection error`, timeout, `WinError 10013`), o backend retorna mensagem amigável:
  - `Não foi possível conectar à OpenAI neste ambiente. Verifique firewall, antivírus, proxy ou rode o app em ambiente com acesso externo.`
- A interface não quebra:
  - o modal mostra `IA indisponível neste ambiente`;
  - mantém opção de fallback local/demonstrativo (`/api/leads/<id>/analisar`).

## Script de validação

Arquivo: `test_openai_connection.py`

Ele testa:
1. se `OPENAI_API_KEY` existe;
2. se o ambiente alcança `api.openai.com`;
3. se uma chamada mínima à OpenAI funciona.

Execução:

```powershell
python test_openai_connection.py
```

## Produção / deploy

- Em produção, configure variáveis de ambiente no servidor/plataforma de deploy:
  - `OPENAI_API_KEY`
  - `SECRET_KEY`
  - `APIFY_API_TOKEN` (se usado no ambiente)
- Garanta saída HTTPS para `api.openai.com` sem bloqueio de firewall/proxy corporativo.
