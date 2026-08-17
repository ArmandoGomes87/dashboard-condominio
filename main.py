import os
import re
import json
from datetime import datetime

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright


PORTAL_URL = os.environ.get("PORTAL_URL", "http://servc7-1.webware.com.br/bin/administradora/")
SICOND_USER = os.environ.get("SICOND_USER", "")
SICOND_PASSWORD = os.environ.get("SICOND_PASSWORD", "")
SHEET_ID = os.environ.get("SHEET_ID", "")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS", "")

ARTIFACT_DIR = "diagnostico"


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def conectar_planilha():
    cred_json = json.loads(GOOGLE_CREDENTIALS)

    with open("cred.json", "w", encoding="utf-8") as f:
        json.dump(cred_json, f)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name("cred.json", scope)
    client = gspread.authorize(creds)

    return client.open_by_key(SHEET_ID)


def obter_ou_criar_aba(spreadsheet, nome):
    try:
        return spreadsheet.worksheet(nome)
    except Exception:
        return spreadsheet.add_worksheet(title=nome, rows=1000, cols=20)


def registrar_log(mensagem, status="INFO"):
    print(f"[{status}] {mensagem}")

    try:
        spreadsheet = conectar_planilha()
        aba = obter_ou_criar_aba(spreadsheet, "Log_Execucao")

        valores = aba.get_all_values()

        if not valores:
            aba.append_row(["DataHora", "Status", "Mensagem"])

        aba.append_row([agora(), status, mensagem])

    except Exception as erro:
        print(f"[ERRO] Falha ao registrar log: {erro}")


def salvar_print(page, nome):
    import os
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    nome_limpo = re.sub(r"[^a-zA-Z0-9_-]", "_", nome)

    try:
        page.screenshot(
            path=f"{ARTIFACT_DIR}/{nome_limpo}.png",
            full_page=True
        )
    except Exception as erro:
        print(f"[ALERTA] Erro ao salvar print: {erro}")

    try:
        html = page.content()
        with open(f"{ARTIFACT_DIR}/{nome_limpo}.html", "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as erro:
        print(f"[ALERTA] Erro ao salvar HTML: {erro}")


def registrar_login_ok_na_base():
    spreadsheet = conectar_planilha()
    aba = obter_ou_criar_aba(spreadsheet, "Base_Mensal")

    aba.append_row([
        "2026",
        "Login Sicond OK",
        "0",
        "0",
        "0",
        "0",
        "0"
    ])


def main():
    registrar_log("Iniciando robô Sicond", "INFO")
    registrar_log(f"URL utilizada: {PORTAL_URL}", "INFO")

    if not SICOND_USER:
        registrar_log("Secret SICOND_USER não encontrado", "ERRO")
        return

    if not SICOND_PASSWORD:
        registrar_log("Secret SICOND_PASSWORD não encontrado", "ERRO")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1366, "height": 768}
        )

        page = context.new_page()

        try:
            page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=60000)
            registrar_log("Tela de login carregada", "OK")
            salvar_print(page, "01_tela_login")
        except Exception as erro:
            registrar_log(f"Erro ao abrir o portal: {erro}", "ERRO")
            salvar_print(page, "erro_ao_abrir_portal")
            browser.close()
            return

        try:
            page.locator("input").nth(0).fill(SICOND_USER)
            page.locator("input").nth(1).fill(SICOND_PASSWORD)

            registrar_log("Usuário e senha preenchidos", "OK")
            salvar_print(page, "02_login_preenchido")

            page.get_by_text("ENTRAR").click(timeout=10000)

            page.wait_for_timeout(8000)

            salvar_print(page, "03_apos_login")

            url_atual = page.url
            registrar_log(f"URL após login: {url_atual}", "INFO")

            if "areadosindico" in url_atual or "asPrincipal.asp" in url_atual:
                registrar_log("Login realizado com sucesso", "OK")
                registrar_login_ok_na_base()
            else:
                registrar_log("Login não confirmado. Verificar prints do diagnóstico.", "ALERTA")

        except Exception as erro:
            registrar_log(f"Erro durante login: {erro}", "ERRO")
            salvar_print(page, "erro_login")

        browser.close()

    registrar_log("Execução finalizada", "OK")


if __name__ == "__main__":
    main()
