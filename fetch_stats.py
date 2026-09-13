"""
Busca as estatisticas do clube no Pro Clubs (EA Sports FC) e salva em stats.json.

Por que via navegador de verdade (Playwright) e nao so "requests"?
A EA esconde a API atras da Akamai, que bloqueia (403 Access Denied) chamadas
HTTP que nao tenham a "impressao digital" de um navegador real (TLS, JS, etc).
Um script Python comum, mesmo copiando os cabecalhos de um Chrome, ainda e
identificado e barrado. Um Chromium de verdade (headless) passa por isso porque
e, literalmente, um navegador de verdade fazendo a chamada.

CONFIGURE AQUI EMBAIXO o nome exato do clube (igual esta dentro do jogo) e a plataforma.
"""

import json
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

# ---------------- CONFIGURE AQUI ----------------
CLUB_NAME = "Aplaca"      # nome EXATO do clube dentro do jogo
PLATFORM = "common-gen5"  # common-gen5 = PS5 / Xbox Series X|S / PC
                           # (se o time joga no PS4/Xbox One, troque para "common-gen4")
# -------------------------------------------------

BASE = "https://proclubs.ea.com/api/fc"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

FETCH_JS = """
    async (url) => {
        try {
            const res = await fetch(url, { headers: { 'accept': 'application/json' } });
            const text = await res.text();
            return { ok: res.ok, status: res.status, text: text };
        } catch (e) {
            return { ok: false, status: 0, text: String(e) };
        }
    }
"""


def fetch_json(page, url, label):
    """Roda um fetch() de dentro da pagina ja carregada (mesma origem da EA).
    Retorna (dados_ou_None, debug)."""
    out = page.evaluate(FETCH_JS, url)
    debug = {"url": url, "status": out.get("status")}
    if not out.get("ok"):
        debug["body"] = (out.get("text") or "")[:800]
        print(f"[aviso] {label} falhou: status {out.get('status')}")
        return None, debug
    try:
        return json.loads(out["text"]), debug
    except Exception as e:
        debug["parse_error"] = str(e)
        debug["body"] = (out.get("text") or "")[:800]
        print(f"[aviso] {label} veio com corpo que nao e JSON: {e}")
        return None, debug


def extract_club_id(search_result):
    """A resposta da busca pode vir como dict {clubId: info} ou como lista."""
    if not search_result:
        return None, None
    if isinstance(search_result, dict):
        for cid, info in search_result.items():
            return cid, info
    if isinstance(search_result, list) and search_result:
        first = search_result[0]
        cid = first.get("clubId") or (first.get("clubInfo") or {}).get("clubId")
        return cid, first
    return None, None


def main():
    result = {
        "club_name_searched": CLUB_NAME,
        "platform": PLATFORM,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "found": False,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)

        # Carrega o site de verdade primeiro -- isso deixa a Akamai ver uma
        # visita "normal" e da tempo pra qualquer cookie/checagem dela rodar,
        # antes da gente chamar a API de dentro dessa mesma pagina.
        try:
            page.goto("https://proclubs.ea.com/", wait_until="networkidle", timeout=30000)
        except Exception as e:
            result["error"] = f"Nao consegui nem abrir o proclubs.ea.com: {e}"
            browser.close()
            write(result)
            return

        search_url = f"{BASE}/allTimeLeaderboard/search?platform={PLATFORM}&clubName={CLUB_NAME}"
        search, search_debug = fetch_json(page, search_url, "busca do clube")

        club_id, club_info = extract_club_id(search)

        if not club_id:
            result["error"] = (
                "Clube nao encontrado (ou a EA ainda bloqueou a chamada). "
                "Veja debug_search_http pra saber qual dos dois foi."
            )
            result["debug_search_raw"] = search
            result["debug_search_http"] = search_debug
            browser.close()
            write(result)
            return

        result["found"] = True
        result["club_id"] = club_id
        result["club_info"] = club_info

        overall, _ = fetch_json(
            page, f"{BASE}/clubs/overallStats?platform={PLATFORM}&clubIds={club_id}", "estatisticas gerais"
        )
        if overall:
            result["overall_stats"] = overall

        details, _ = fetch_json(
            page, f"{BASE}/clubs/info?platform={PLATFORM}&clubIds={club_id}", "detalhes do clube"
        )
        if details:
            result["club_details"] = details

        league_matches, _ = fetch_json(
            page,
            f"{BASE}/clubs/matches?platform={PLATFORM}&clubIds={club_id}&matchType=leagueMatch&maxResultCount=10",
            "partidas de liga",
        )
        if league_matches:
            result["league_matches"] = league_matches

        friendly_matches, _ = fetch_json(
            page,
            f"{BASE}/clubs/matches?platform={PLATFORM}&clubIds={club_id}&matchType=friendlyMatch&maxResultCount=10",
            "partidas amistosas",
        )
        if friendly_matches:
            result["friendly_matches"] = friendly_matches

        browser.close()

    write(result)


def write(result):
    with open("stats.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("stats.json salvo.")


if __name__ == "__main__":
    main()
