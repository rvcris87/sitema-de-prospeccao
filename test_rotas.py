"""Teste simples das rotas logadas.

Faz login (via /demo-login) e dá GET em todas as rotas, esperando status 200.
Roda numa CÓPIA temporária do leads.db (ou num banco vazio), nunca no banco real.

Uso:
    python test_rotas.py
    python -m unittest test_rotas -v
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

# O caminho do banco precisa estar definido ANTES de importar o app.
_TMP_DIR = tempfile.mkdtemp(prefix="radar_teste_")
_DB_TESTE = Path(_TMP_DIR) / "leads_teste.db"
_DB_REAL = Path(__file__).resolve().parent / "leads.db"
if _DB_REAL.exists():
    shutil.copy(_DB_REAL, _DB_TESTE)
os.environ["DATABASE_PATH"] = str(_DB_TESTE)

import app as app_module  # noqa: E402

ROTAS_LOGADAS = [
    "/dashboard",
    "/app",
    "/leads",
    "/leads?status=Novo",
    "/leads?q=a&cidade=xyz",
    "/leads?aprovacao=sim",
    "/mensagens",
    "/configuracoes",
    "/buscar-leads",
    "/capturar-leads",
    "/importar-apify",
    "/leads/novo",
    "/api/leads",
    "/api/leads?q=barbearia",
]

ROTAS_PUBLICAS = ["/login", "/cadastro", "/health"]

# Etapa 2.3: rotas antigas continuam existindo, mas só redirecionam.
ROTAS_REDIRECIONADAS = {
    "/laudos": "/leads?aprovacao=sim",
    "/oportunidades": "/leads",
    "/insights": "/app",  # url_for("dashboard") resolve para /app
}


class TestRotas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = app_module.app
        cls.app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def logado(self):
        client = self.app.test_client()
        resposta = client.get("/demo-login")
        self.assertEqual(resposta.status_code, 302, "demo-login deveria redirecionar")
        return client

    def test_rotas_publicas(self):
        client = self.app.test_client()
        for rota in ROTAS_PUBLICAS:
            with self.subTest(rota=rota):
                self.assertEqual(client.get(rota).status_code, 200)

    def test_rotas_logadas_5_vezes(self):
        client = self.logado()
        for rodada in range(5):
            for rota in ROTAS_LOGADAS:
                with self.subTest(rota=rota, rodada=rodada + 1):
                    resposta = client.get(rota)
                    self.assertEqual(resposta.status_code, 200, f"{rota} -> {resposta.status_code}")

    def test_rotas_antigas_redirecionam(self):
        client = self.logado()
        for rota, destino in ROTAS_REDIRECIONADAS.items():
            with self.subTest(rota=rota):
                resposta = client.get(rota)
                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(resposta.headers["Location"].endswith(destino), resposta.headers["Location"])

    def test_menu_enxuto_e_sem_demo(self):
        client = self.app.test_client()
        for rota in ("/", "/login"):
            with self.subTest(rota=rota):
                self.assertNotIn("demo-login", client.get(rota).get_data(as_text=True))
        html = self.logado().get("/dashboard").get_data(as_text=True)
        for rota in ROTAS_REDIRECIONADAS:
            with self.subTest(rota=rota):
                self.assertNotIn(f'href="{rota}"', html)

    def test_rotas_do_lead(self):
        client = self.logado()
        leads = client.get("/api/leads").get_json()["leads"]
        if not leads:
            self.skipTest("Banco sem leads para testar detalhe/edição.")
        lead_id = leads[0]["id"]
        for rota in (f"/api/leads/{lead_id}", f"/leads/{lead_id}/editar"):
            with self.subTest(rota=rota):
                self.assertEqual(client.get(rota).status_code, 200)
        self.assertEqual(client.get("/api/leads/99999999").status_code, 404)

    def test_filtro_aprovacao(self):
        client = self.logado()
        leads = client.get("/api/leads?aprovacao=sim").get_json()["leads"]
        for lead in leads:
            self.assertEqual(lead["_status_geral"], "Aprovado")

    def test_plano_vem_do_banco(self):
        client = self.logado()
        with app_module.get_connection() as connection:
            antigo = connection.execute(
                "SELECT plano FROM users WHERE email = ?", ("demo@radarlocal.com",)
            ).fetchone()["plano"]
            connection.execute(
                "UPDATE users SET plano = ? WHERE email = ?", ("Plano Mudado", "demo@radarlocal.com")
            )
        try:
            self.assertIn("Plano Mudado", client.get("/dashboard").get_data(as_text=True))
        finally:
            with app_module.get_connection() as connection:
                connection.execute(
                    "UPDATE users SET plano = ? WHERE email = ?", (antigo, "demo@radarlocal.com")
                )

    def test_sem_login_redireciona(self):
        client = self.app.test_client()
        self.assertEqual(client.get("/dashboard").status_code, 302)

    def test_pagina_de_erro_500(self):
        client = self.logado()
        original = app_module.get_metrics

        def quebra(*args, **kwargs):
            raise RuntimeError("erro simulado pelo teste")

        app_module.get_metrics = quebra
        # Em TESTING o Flask propaga a exceção; desliga para exercitar o errorhandler(500).
        self.app.config["PROPAGATE_EXCEPTIONS"] = False
        try:
            resposta = client.get("/dashboard")
        finally:
            app_module.get_metrics = original
            self.app.config["PROPAGATE_EXCEPTIONS"] = None
        self.assertEqual(resposta.status_code, 500)
        self.assertIn("Algo deu errado", resposta.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
