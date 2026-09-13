"""
Busca as estatisticas do clube no Pro Clubs (EA Sports FC) e salva em stats.json.

Este script roda dentro do GitHub Actions (veja .github/workflows/update-stats.yml),
nao no navegador -- e por isso ele consegue falar com a API da EA sem ser bloqueado.

CONFIGURE AQUI EMBAIXO o nome exato do clube (igual esta dentro do jogo) e a plataforma.
"""

import json
import sys
from datetime import datetime, timezone

import requests

# ---------------- CONFIGURE AQUI ----------------
CLUB_NAME = "Aplaca"     # nome EXATO do clube dentro do jogo
PLATFORM = "common-gen5"       # common-gen5 = PS5 / Xbox Series X|S / PC
                                # (se o time joga no PS4/Xbox One, troque para "common-gen4")
# -------------------------------------------------

BASE = "https://proclubs.ea.com/api/fc"

HEADERS = {
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9",
    "sec-ch-ua": '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    ),
}


def get(url, params, label):
    """GET defensivo: nunca derruba o script, so avisa no log e segue."""
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[aviso] {label} falhou: {e}", file=sys.stderr)
        return None


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

    search = get(
        f"{BASE}/allTimeLeaderboard/search",
        {"platform": PLATFORM, "clubName": CLUB_NAME},
        "busca do clube",
    )

    club_id, club_info = extract_club_id(search)

    if not club_id:
        result["error"] = (
            "Clube nao encontrado. Confira se CLUB_NAME esta escrito exatamente "
            "igual ao nome do clube dentro do jogo, e se PLATFORM esta certo."
        )
        # guarda a resposta crua da EA pra dar pra debugar o que realmente voltou
        result["debug_search_raw"] = search
        write(result)
        return

    result["found"] = True
    result["club_id"] = club_id
    result["club_info"] = club_info

    overall = get(
        f"{BASE}/clubs/overallStats",
        {"platform": PLATFORM, "clubIds": club_id},
        "estatisticas gerais",
    )
    if overall:
        result["overall_stats"] = overall

    details = get(
        f"{BASE}/clubs/info",
        {"platform": PLATFORM, "clubIds": club_id},
        "detalhes do clube",
    )
    if details:
        result["club_details"] = details

    league_matches = get(
        f"{BASE}/clubs/matches",
        {"platform": PLATFORM, "clubIds": club_id, "matchType": "leagueMatch", "maxResultCount": 10},
        "partidas de liga",
    )
    if league_matches:
        result["league_matches"] = league_matches

    friendly_matches = get(
        f"{BASE}/clubs/matches",
        {"platform": PLATFORM, "clubIds": club_id, "matchType": "friendlyMatch", "maxResultCount": 10},
        "partidas amistosas",
    )
    if friendly_matches:
        result["friendly_matches"] = friendly_matches

    write(result)


def write(result):
    with open("stats.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("stats.json salvo.")


if __name__ == "__main__":
    main()
