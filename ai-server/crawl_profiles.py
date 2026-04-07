"""
K리그1 선수 프로필 수집 스크립트 — Wikipedia 기반.

수집 항목:
  - 이름(영문), 팀, 포지션, 등번호, 국적(IOC 3자리 코드 → 국가명)
  - 생년월일·나이·신장 (Wikipedia 개인 문서에서 추가 수집)
  - 이적 이력 (Wikipedia 개인 문서에서 추가 수집)

출력: data/processed/players/player_profiles.json

사용법:
  python crawl_profiles.py              # K1 전체 수집 (기본)
  python crawl_profiles.py --dry-run    # 첫 팀만 테스트
  python crawl_profiles.py --enrich     # 개인 문서에서 생년월일 등 추가 수집 (느림)
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, date
from pathlib import Path

import requests
from loguru import logger

logger.remove()
sys.stderr.reconfigure(encoding="utf-8")
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | {level} | {message}")

BASE_DIR = Path(__file__).parent
OUT_DIR  = BASE_DIR / "data" / "processed" / "players"
OUT_PATH = OUT_DIR / "player_profiles.json"

sys.path.insert(0, str(BASE_DIR))
from crawlers.config.teams import K1_TEAMS

# ── IOC 국적 코드 → 국가명 매핑 (K리그 등장 국가 중심) ──────────────
NAT_MAP: dict[str, str] = {
    "KOR": "대한민국", "BRA": "브라질", "NGA": "나이지리아", "CHN": "중국",
    "JPN": "일본",    "COL": "콜롬비아", "ARG": "아르헨티나", "URU": "우루과이",
    "GHA": "가나",    "CMR": "카메룬",  "CIV": "코트디부아르", "SEN": "세네갈",
    "USA": "미국",    "AUS": "호주",    "FRA": "프랑스",     "SPA": "스페인",
    "ESP": "스페인",  "POR": "포르투갈", "GER": "독일",       "ITA": "이탈리아",
    "SWE": "스웨덴",  "DEN": "덴마크",  "NED": "네덜란드",   "CRO": "크로아티아",
    "SRB": "세르비아","BIH": "보스니아", "MNE": "몬테네그로", "MKD": "북마케도니아",
    "RUS": "러시아",  "UKR": "우크라이나","GEO": "조지아",   "ARM": "아르메니아",
    "KAZ": "카자흐스탄","UZB":"우즈베키스탄","TJK":"타지키스탄",
    "GAB": "가봉",    "COD": "콩고민주공화국","MLI":"말리","TOG":"토고",
    "GAM": "감비아",  "GNB": "기니비사우","CAN":"캐나다","MEX":"멕시코",
    "ECU": "에콰도르","PAR":"파라과이",  "BOL":"볼리비아","PER":"페루",
    "CHI": "칠레",    "VEN":"베네수엘라","HAI":"아이티","JAM":"자메이카",
    "TRI": "트리니다드 토바고","CRC":"코스타리카",
    "NZL": "뉴질랜드","FIJ":"피지",
    "KGZ": "키르기스스탄","MGL":"몽골","PRK":"북한","VIE":"베트남",
    "THA": "태국",    "IDN":"인도네시아","MYS":"말레이시아","PHI":"필리핀",
    "ISL": "아이슬란드","IRL":"아일랜드","SCO":"스코틀랜드","WAL":"웨일스",
    "ENG": "잉글랜드","NIR":"북아일랜드",
}

POSITION_MAP = {
    "GK": "GK", "DF": "DF", "MF": "MF", "FW": "FW", "AM": "MF", "DM": "MF",
}

# ── Wikipedia 파싱 ─────────────────────────────────────────────

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_HEADERS = {"User-Agent": "KLeagueProfileCrawler/1.0 (research)"}


def fetch_wiki_content(title: str) -> str:
    """Wikipedia 문서 위키텍스트 가져오기"""
    r = requests.get(WIKI_API, params={
        "action": "query", "titles": title,
        "prop": "revisions", "rvprop": "content",
        "format": "json", "formatversion": "2",
        "redirects": "1",
    }, headers=WIKI_HEADERS, timeout=15)
    data = r.json()
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return ""
    revisions = pages[0].get("revisions", [])
    return revisions[0].get("content", "") if revisions else ""


def parse_squad_from_wiki(content: str, team_short: str, team_name_ko: str) -> list[dict]:
    """
    {{Fs player|no=21|nat=KOR|name=[[Jo Hyeon-woo]]|pos=GK}}
    형태 파싱 → 선수 목록 반환
    """
    players = []
    pattern = re.compile(
        r'\{\{Fs player\s*\|([^}]+)\}\}', re.IGNORECASE
    )
    for m in pattern.finditer(content):
        raw = m.group(1)
        fields = _parse_template_fields(raw)
        name_raw = fields.get("name", "")
        # [[Link|Display]] or [[Link]] 처리
        name = re.sub(r'\[\[(?:[^|\]]+\|)?([^\]]+)\]\]', r'\1', name_raw).strip()
        # 위키링크 슬러그 추출 (개인 문서 접근용)
        link_m = re.search(r'\[\[([^\]|]+)', name_raw)
        wiki_slug = link_m.group(1).strip() if link_m else None

        nat_code = fields.get("nat", "").upper()
        pos_code  = fields.get("pos", "").upper()
        jersey    = fields.get("no", "")
        on_loan   = "loan" in fields.get("other", "").lower()
        captain   = "captain" in fields.get("other", "").lower()

        players.append({
            "name_en":      name,
            "name_ko":      "",          # 개별 문서에서 보강
            "team":         team_name_ko,
            "team_short":   team_short,
            "jersey_number": jersey,
            "position":     POSITION_MAP.get(pos_code, pos_code),
            "nationality_code": nat_code,
            "nationality":  NAT_MAP.get(nat_code, nat_code),
            "is_foreign":   nat_code != "KOR",
            "on_loan":      on_loan,
            "captain":      captain,
            "birth_date":   None,
            "age":          None,
            "height_cm":    None,
            "wiki_slug":    wiki_slug,
            "source":       "wikipedia",
            "crawled_at":   datetime.now().strftime("%Y-%m-%d"),
        })
    return players


def _parse_template_fields(raw: str) -> dict[str, str]:
    """
    'no=21|nat=KOR|name=[[Lee|Display]]|pos=GK' → {'no':'21', 'nat':'KOR', 'name':'[[Lee|Display]]', ...}
    [[...]] 내부의 | 를 무시하면서 파싱.
    """
    result = {}
    # [[...]] 블록을 임시 치환해서 | 가 분리되지 않도록 처리
    placeholder_map: dict[str, str] = {}
    def replace_link(m: re.Match) -> str:
        key = f"\x00LINK{len(placeholder_map)}\x00"
        placeholder_map[key] = m.group(0)
        return key
    sanitized = re.sub(r'\[\[[^\]]*\]\]', replace_link, raw)

    for part in sanitized.split("|"):
        if "=" in part:
            k, _, v = part.partition("=")
            # 플레이스홀더 복원
            for ph, orig in placeholder_map.items():
                v = v.replace(ph, orig)
            result[k.strip().lower()] = v.strip()
    return result


# ── 개인 문서 보강 (생년월일·신장·한국어 이름) ────────────────────

def enrich_from_personal_page(player: dict) -> dict:
    """
    선수 Wikipedia 개인 문서에서 생년월일·신장·한국어 이름 추가.
    """
    slug = player.get("wiki_slug")
    if not slug:
        return player

    try:
        content = fetch_wiki_content(slug)
        if not content:
            return player

        # 생년월일: {{birth date and age|1990|5|14}} 또는 {{birth date|...}}
        bd_m = re.search(
            r'\{\{birth date(?:\s+and\s+age)?\s*\|(\d{4})\|(\d{1,2})\|(\d{1,2})',
            content, re.IGNORECASE
        )
        if bd_m:
            y, mo, d = bd_m.groups()
            player["birth_date"] = f"{y}-{int(mo):02d}-{int(d):02d}"
            player["age"] = datetime.now().year - int(y)

        # 신장: | height = {{convert|183|cm|...}} or | height_m = 1.83
        ht_m = re.search(r'height\s*=\s*\{\{convert\|(\d{2,3})\|cm', content, re.IGNORECASE)
        if ht_m:
            player["height_cm"] = int(ht_m.group(1))
        else:
            ht_m2 = re.search(r'height_m\s*=\s*([\d.]+)', content, re.IGNORECASE)
            if ht_m2:
                player["height_cm"] = int(float(ht_m2.group(1)) * 100)

        # 한국어 이름: | hangul = 조현우 or 첫 번째 ko: 링크
        ko_m = re.search(r'(?:hangul|korean)\s*=\s*([^\n|}\]]+)', content, re.IGNORECASE)
        if ko_m:
            player["name_ko"] = ko_m.group(1).strip()

    except Exception as e:
        logger.debug(f"개인 문서 보강 실패: {player.get('name_en')} | {e}")

    return player


# ── 팀 Wikipedia 페이지 제목 탐색 ─────────────────────────────────

def get_squad(team, enrich: bool = False, delay: float = 1.5) -> list[dict]:
    """팀 Wikipedia 문서에서 선수단 파싱"""
    # 영문 Wikipedia 제목 시도
    wiki_title = team.wikipedia_en.replace("_", " ")
    content = fetch_wiki_content(wiki_title)
    if not content:
        logger.warning(f"  위키 문서 없음: {wiki_title}")
        return []

    players = parse_squad_from_wiki(content, team.short_name, team.name_ko)
    logger.info(f"  {team.short_name}: {len(players)}명 파싱")

    if enrich:
        for i, p in enumerate(players):
            players[i] = enrich_from_personal_page(p)
            time.sleep(delay)

    return players


# ── 메인 ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="K리그1 선수 프로필 수집 (Wikipedia)")
    parser.add_argument("--dry-run", action="store_true", help="첫 팀만 테스트")
    parser.add_argument("--enrich",  action="store_true", help="개인 문서에서 생년월일·신장 추가 수집")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    teams = K1_TEAMS[:1] if args.dry_run else K1_TEAMS
    all_players: list[dict] = []

    logger.info(f"{'[DRY-RUN] ' if args.dry_run else ''}K1 {len(teams)}개 팀 수집 시작")
    logger.info(f"개인 문서 보강: {'ON' if args.enrich else 'OFF (--enrich 옵션 추가 시 활성화)'}")

    for team in teams:
        logger.info(f"▶ {team.name_ko}")
        players = get_squad(team, enrich=args.enrich)
        all_players.extend(players)
        time.sleep(1.0)  # Wikipedia 요청 간 딜레이

    if not all_players:
        logger.error("수집된 선수 없음")
        sys.exit(1)

    # 요약
    total = len(all_players)
    foreign = sum(1 for p in all_players if p["is_foreign"])
    nat_dist: dict[str, int] = {}
    for p in all_players:
        n = p["nationality"]
        nat_dist[n] = nat_dist.get(n, 0) + 1

    logger.info(f"총 {total}명 | 외국인 {foreign}명 | 내국인 {total - foreign}명")
    logger.info(f"국적 분포: {dict(sorted(nat_dist.items(), key=lambda x: -x[1])[:10])}")

    if args.dry_run:
        logger.info("[DRY-RUN] 저장 생략 — 샘플:")
        for p in all_players[:5]:
            print(json.dumps(p, ensure_ascii=False, indent=2))
        return

    out = {
        "crawled_at":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        "season":        2026,
        "league":        "K1",
        "source":        "wikipedia",
        "total_players": total,
        "players":       all_players,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.success(f"저장 완료: {OUT_PATH}  ({total}명)")


if __name__ == "__main__":
    main()
