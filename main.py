import os
import re
import json
from datetime import datetime

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright


PORTAL_URL = os.environ.get(
    "PORTAL_URL",
    "http://servc7-1.webware.com.br/bin/administradora/"
)

SICOND_USER = os.environ.get("SICOND_USER", "")
SICOND_PASSWORD = os.environ.get("SICOND_PASSWORD", "")

SHEET_ID = os.environ.get("SHEET_ID", "")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS", "")

ARTIFACT_DIR = "diagnostico"
DOWNLOAD_DIR = "downloads"


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def criar_pastas():
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def conectar_planilha():
    cred_json = json.loads(GOOGLE_CREDENTIALS)

    with open("cred.json", "w", encoding="utf-8") as f:
        json.dump(cred_json, f)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "cred.json",
        scope
    )

    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)


def obter_ou_criar_aba(spreadsheet, nome, linhas=1000, colunas=20):
    try:
        return spreadsheet.worksheet(nome)
    except Exception:
        return spreadsheet.add_worksheet(
            title=nome,
            rows=linhas,
            cols=colunas
        )


def registrar_log(mensagem, status="INFO"):
    print(f"[{status}] {mensagem}")

    try:
        spreadsheet = conectar_planilha()
        aba = obter_ou_criar_aba(spreadsheet, "Log_Execucao")

        valores = aba.get_all_values()

        if not valores:
            aba.append_row(["DataHora", "Status", "Mensagem"])

        aba.append_row([
            agora(),
            status,
            mensagem
        ])

    except Exception as erro:
        print(f"[ERRO] Falha ao registrar log na planilha: {erro}")


def salvar_estado_pagina(page, nome):
    nome_limpo = re.sub(r"[^a-zA-Z0-9_-]", "_", nome)

    try:
        page.screenshot(
            path=f"{ARTIFACT_DIR}/{nome_limpo}.png",
            full_page=True
        )
    except Exception as erro:
        print(f"[ALERTA] Falha ao salvar screenshot: {erro}")

    try:
        html = page.content()
        with open(
            f"{ARTIFACT_DIR}/{nome_limpo}.html",
            "w",
            encoding="utf-8"
        ) as f:
            f.write(html)
    except Exception as erro:
        print(f"[ALERTA] Falha ao salvar HTML: {erro}")


def listar_elementos(page, nome):
    nome_limpo = re.sub(r"[^a-zA-Z0-9_-]", "_", nome)
    caminho = f"{ARTIFACT_DIR}/{nome_limpo}_elementos.txt"

    linhas = []

    for indice, frame in enumerate(page.frames):
        linhas.append(f"\n===== FRAME {indice} =====")
        linhas.append(f"URL: {frame.url}\n")

        try:
            inputs = frame.locator("input").evaluate_all("""
                els => els.map((e, idx) => ({
                    idx: idx,
                    type: e.getAttribute('type'),
                    name: e.getAttribute('name'),
                    id: e.getAttribute('id'),
                    placeholder: e.getAttribute('placeholder'),
                    value: e.getAttribute('value')
                }))
            """)
            linhas.append("INPUTS:")
            linhas.append(json.dumps(inputs, indent=2, ensure_ascii=False))
        except Exception as erro:
            linhas.append(f"Erro ao listar inputs: {erro}")

        try:
            botoes_links = frame.locator("button, input[type='submit'], a, div").evaluate_all("""
                els => els.slice(0, 300).map((e, idx) => ({
                    idx: idx,
                    tag: e.tagName,
                    text: (e.innerText || e.value || '').trim(),
                    href: e.getAttribute('href'),
                    name: e.getAttribute('name'),
                    id: e.getAttribute('id'),
                    className: e.getAttribute('class'),
                    type: e.getAttribute('type')
                }))
            """)
            linhas.append("\nBOTOES_LINKS_DIVS:")
            linhas.append(json.dumps(botoes_links, indent=2, ensure_ascii=False))
        except Exception as erro:
            linhas.append(f"Erro ao listar botoes/links/divs: {erro}")

    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))


def preencher_login(page):
    usuario_preenchido = False
    senha_preenchida = False

    seletores_usuario = [
        "input[placeholder='Usuário']",
        "input[placeholder='Usuario']",
        "input[name*='usuario' i]",
        "input[id*='usuario' i]",
        "input[name*='login' i]",
        "input[id*='login' i]",
        "input[type='text']"
    ]

    seletores_senha = [
        "input[placeholder='Senha']",
        "input[name*='senha' i]",
        "input[id*='senha' i]",
        "input[type='password']"
    ]

    for seletor in seletores_usuario:
        try:
            page.locator(seletor).first.fill(SICOND_USER, timeout=3000)
            usuario_preenchido = True
            break
        except Exception:
            pass

    for seletor in seletores_senha:
        try:
            page.locator(seletor).first.fill(SICOND_PASSWORD, timeout=3000)
            senha_preenchida = True
            break
        except Exception:
            pass

    return usuario_preenchido, senha_preenchida


def clicar_entrar(page):
    tentativas = [
        lambda: page.get_by_text("ENTRAR").click(timeout=5000),
        lambda: page.get_by_text("Entrar").click(timeout=5000),
        lambda: page.locator("button").first.click(timeout=5000),
        lambda: page.locator("input[type='submit']").first.click(timeout=5000),
        lambda: page.keyboard.press("Enter")
    ]

    for tentativa in tentativas:
        try:
            tentativa()
            return True
        except Exception:
            pass

    return False


def clicar_texto(page, textos):
    for texto in textos:
        try:
            page.get_by_text(
                re.compile(texto, re.IGNORECASE)
            ).first.click(timeout=5000)
            return True, texto
        except Exception:
            pass

    for frame in page.frames:
        for texto in textos:
            try:
                frame.get_by_text(
                    re.compile(texto, re.IGNORECASE)
                ).first.click(timeout=5000)
                return True, texto
            except Exception:
                pass

    return False, None


def tentar_baixar_excel(page):
    textos_exportacao = [
        "Exportar Excel",
        "Exportar",
        "Excel",
        "XLS",
        "XLSX",
        "Baixar"
    ]

    for texto in textos_exportacao:
        try:
            with page.expect_download(timeout=10000) as download_info:
                page.get_by_text(
                    re.compile(texto, re.IGNORECASE)
                ).first.click(timeout=5000)

            download = download_info.value
            nome_arquivo = download.suggested_filename or "prestacao_contas.xlsx"
            caminho = os.path.join(DOWNLOAD_DIR, nome_arquivo)
            download.save_as(caminho)

            registrar_log(f"Arquivo baixado: {nome_arquivo}", "OK")
            return caminho

        except Exception:
            pass

    return None


def registrar_teste_base_mensal():
    spreadsheet = conectar_planilha()
    aba = obter_ou_criar_aba(spreadsheet, "Base_Mensal")

    valores = aba.get_all_values()

    if not valores:
        aba.append_row([
            "Ano",
            "Mês",
            "Receita",
            "Despesa",
            "Resultado",
            "Fundo Reserva",
            "Inadimplência"
        ])

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
    criar_pastas()

    registrar_log("Iniciando robô Sicond", "INFO")
    registrar_log(f"URL utilizada: {PORTAL_URL}", "INFO")

    if not SICOND_USER:
        registrar_log("Secret SICOND_USER não configurado", "ERRO")
        return

    if not SICOND_PASSWORD:
        registrar_log("Secret SICOND_PASSWORD não configurado", "ERRO")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            ignore_https_errors=True,
            accept_downloads=True,
            viewport={"width": 1366, "height": 768}
        )

        page = context.new_page()

        try:
            page.goto(
                PORTAL_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            registrar_log("Tela de login carregada", "OK")
            salvar_estado_pagina(page, "01_tela_login")
            listar_elementos(page, "01_tela_login")

        except Exception as erro:
            registrar_log(f"Erro ao abrir portal: {erro}", "ERRO")
            salvar_estado_pagina(page, "erro_abrir_portal")
            browser.close()
            return

        try:
            usuario_ok, senha_ok = preencher_login(page)

            registrar_log(
                f"Campos preenchidos - usuario: {usuario_ok}, senha: {senha_ok}",
                "INFO"
            )

            salvar_estado_pagina(page, "02_login_preenchido")

            clicou = clicar_entrar(page)
            registrar_log(f"Clique no botão ENTRAR: {clicou}", "INFO")

            page.wait_for_timeout(7000)

            salvar_estado_pagina(page, "03_apos_login")
            listar_elementos(page, "03_apos_login")

            url_atual = page.url
            registrar_log(f"URL após login: {url_atual}", "INFO")

            if "asPrincipal.asp" in url_atual or "areadosindico" in url_atual:
                registrar_log("Login aparentemente realizado com sucesso", "OK")
                registrar_teste_base_mensal()
            else:
                registrar_log("Login pode não ter sido concluído. Verificar diagnóstico.", "ALERTA")

        except Exception as erro:
            registrar_log(f"Erro durante login: {erro}", "ERRO")
            salvar_estado_pagina(page, "erro_login")
            browser.close()
            return

        try:
            clicou_prestacao, texto_usado = clicar_texto(
                page,
                [
                    "PRESTAÇÃO DE CONTAS",
                    "PRESTACAO DE CONTAS",
                    "Prestação de Contas",
                    "Prestacao de Contas"
                ]
            )

            registrar_log(
                f"Clique em Prestação de Contas: {clicou_prestacao} - {texto_usado}",
                "INFO"
            )

            page.wait_for_timeout(7000)

            salvar_estado_pagina(page, "04_apos_prestacao_contas")
            listar_elementos(page, "04_apos_prestacao_contas")

        except Exception as erro:
            registrar_log(f"Erro ao clicar em Prestação de Contas: {erro}", "ERRO")
            salvar_estado_pagina(page, "erro_prestacao")

        try:
            arquivo = tentar_baixar_excel(page)

            if arquivo:
                registrar_log(f"Download encontrado em: {arquivo}", "OK")
            else:
                registrar_log(
                    "Nenhum botão de exportação Excel localizado nesta execução",
                    "ALERTA"
                )
                salvar_estado_pagina(page, "05_sem_excel")
                listar_elementos(page, "05_sem_excel")

        except Exception as erro:
            registrar_log(f"Erro ao tentar download Excel: {erro}", "ERRO")
            salvar_estado_pagina(page, "erro_download")

        browser.close()

    registrar_log("Execução finalizada", "OK")


if __name__ == "__main__":
    main()
