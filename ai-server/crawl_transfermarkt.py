"""
Transfermarkt K리그1 선수 생년월일·신장 수집 스크립트.

흐름:
  1. 각 팀의 /kader/ 페이지 → 선수명·slug·TM ID 수집
  2. 각 선수 /profil/ 페이지 → 생년월일·신장 추출
  3. player_profiles.json과 이름 매칭 → 빈 필드 업데이트

사용법:
  python crawl_transfermarkt.py           # 전체 수집
  python crawl_transfermarkt.py --dry-run # 첫 팀만 테스트
  python crawl_transfermarkt.py --team 울산  # 특정 팀만
"""

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from loguru import logger

sys.stderr.reconfigure(encoding="utf-8")
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | {level} | {message}")

BASE_DIR = Path(__file__).parent
PROFILES = BASE_DIR / "data" / "processed" / "players" / "player_profiles.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.transfermarkt.com/",
}
TM_BASE = "https://www.transfermarkt.com"
DELAY   = 2.0  # 요청 간 딜레이 (초)

# ── K리그1 팀 Transfermarkt 정보 ──────────────────────────────────────
K1_TM_TEAMS = [
    {"name_ko": "전북", "slug": "jeonbuk-hyundai-motors", "tm_id": 6502},
    {"name_ko": "울산", "slug": "ulsan-hyundai",          "tm_id": 3535},
    {"name_ko": "서울", "slug": "fc-seoul",               "tm_id": 6500},
    {"name_ko": "포항", "slug": "pohang-steelers",        "tm_id": 311},
    {"name_ko": "인천", "slug": "incheon-united",         "tm_id": 2996},
    {"name_ko": "수원FC","slug": "suwon-fc",              "tm_id": 31622},
    {"name_ko": "대전", "slug": "daejeon-hana-citizen",   "tm_id": 6499},
    {"name_ko": "광주", "slug": "gwangju-fc",             "tm_id": 30925},
    {"name_ko": "강원", "slug": "gangwon-fc",             "tm_id": 21459},
    {"name_ko": "제주", "slug": "jeju-united",            "tm_id": 19684},
    {"name_ko": "대구", "slug": "daegu-fc",               "tm_id": 6504},
    {"name_ko": "전남", "slug": "jeonnam-dragons",        "tm_id": 6503},
]


# ── HTTP 유틸 ────────────────────────────────────────────────────────

def get(url: str, retries: int = 2) -> requests.Response | None:
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=18)
            if r.status_code == 429:
                logger.warning(f"429 rate limit — {url}")
                time.sleep(30)
                continue
            if r.status_code == 403:
                logger.warning(f"403 forbidden — {url}")
                return None
            if not r.ok:
                logger.debug(f"HTTP {r.status_code} — {url}")
                return None
            return r
        except Exception as e:
            logger.debug(f"요청 실패({attempt+1}): {url} | {e}")
            time.sleep(3)
    return None


# ── 팀 스쿼드 페이지 파싱 ────────────────────────────────────────────

def fetch_squad(team: dict) -> list[dict]:
    """팀 /kader/ 페이지에서 선수 목록(이름·slug·tm_id) 반환."""
    url = f"{TM_BASE}/{team['slug']}/kader/verein/{team['tm_id']}"
    r   = get(url)
    if not r:
        logger.warning(f"스쿼드 페이지 실패: {team['name_ko']}")
        return []

    soup  = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", class_="items")
    if not table:
        logger.warning(f"선수 테이블 없음: {team['name_ko']}")
        return []

    players = []
    for row in table.find_all("tr", class_=["odd", "even"]):
        link = row.find("a", href=re.compile(r"/profil/spieler/\d+"))
        if not link:
            continue
        href = link["href"]          # "/hyeon-woo-jo/profil/spieler/260171"
        m    = re.search(r"/([^/]+)/profil/spieler/(\d+)", href)
        if not m:
            continue
        players.append({
            "name_tm":   link.text.strip(),
            "tm_slug":   m.group(1),
            "tm_id":     int(m.group(2)),
            "team_ko":   team["name_ko"],
        })

    logger.info(f"  {team['name_ko']}: {len(players)}명")
    return players


# ── 선수 프로필 페이지 파싱 ──────────────────────────────────────────

def fetch_player_info(tm_slug: str, tm_id: int) -> dict:
    """선수 /profil/ 페이지에서 생년월일·신장 반환."""
    url = f"{TM_BASE}/{tm_slug}/profil/spieler/{tm_id}"
    r   = get(url)
    if not r:
        return {}

    soup = BeautifulSoup(r.text, "html.parser")
    info_div = soup.find("div", class_="info-table")
    if not info_div:
        return {}

    # 레이블·값 교대로 등장하는 span 리스트를 key→value 매핑으로 변환
    spans  = info_div.find_all("span")
    kv: dict[str, str] = {}
    for i, sp in enumerate(spans):
        cls = sp.get("class", [])
        if "info-table__content--regular" in cls:
            label = sp.text.strip().rstrip(":")
            # 다음 bold span을 값으로 사용
            for j in range(i + 1, min(i + 4, len(spans))):
                c2 = spans[j].get("class", [])
                if "info-table__content--bold" in c2:
                    kv[label] = spans[j].text.strip()
                    break

    result: dict = {}

    # 생년월일: "25/09/1991 (34)" 또는 "Sep 25, 1991 (34)"
    dob_raw = kv.get("Date of birth/Age", "")
    if dob_raw:
        # DD/MM/YYYY 형식
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", dob_raw)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            result["birth_date"] = f"{y:04d}-{mo:02d}-{d:02d}"
            result["age"]        = datetime.now().year - y
        else:
            # "Sep 25, 1991" 형식
            m2 = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", dob_raw)
            if m2:
                MONTHS = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
                          "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
                mo_str = m2.group(1)[:3].title()
                mo = MONTHS.get(mo_str)
                if mo:
                    d  = int(m2.group(2))
                    y  = int(m2.group(3))
                    result["birth_date"] = f"{y:04d}-{mo:02d}-{d:02d}"
                    result["age"]        = datetime.now().year - y

    # 신장: "1,89\xa0m" 또는 "1.89 m" 또는 "189 cm"
    ht_raw = kv.get("Height", "")
    if ht_raw:
        # 1,89 m / 1.89 m 형식
        m = re.search(r"(\d)[,.](\d{2})\s*m", ht_raw.replace("\xa0", " "))
        if m:
            ht = int(m.group(1)) * 100 + int(m.group(2))
            if 140 <= ht <= 220:
                result["height_cm"] = ht
        else:
            # 189 cm 형식
            m2 = re.search(r"(\d{3})\s*cm", ht_raw)
            if m2:
                ht = int(m2.group(1))
                if 140 <= ht <= 220:
                    result["height_cm"] = ht

    return result


# ── 이름 매칭 유틸 ───────────────────────────────────────────────────

# 한국어 로마자 표기 정규화 치환 규칙 (긴 패턴 먼저)
_KO_ROMAN_SUBS: list[tuple[str, str]] = [
    # 모음 통일
    ("eo",  "u"),   # hyeon→hyun, seong→sung, jeong→jung, yeong→yung
    ("ou",  "u"),   # young→yung  (yeong→yung 과 통일)
    ("oo",  "u"),   # yoon→yun, joon→jun, woon→wun
    ("wu",  "u"),   # wun→un (woon→wun→un 체인)
    ("ae",  "e"),   # baek→bek
    ("ck",  "k"),   # back→bak  (then ae→e already done → baek→bek)
    ("jee", "ji"),  # jee→ji
    # 성씨 표기 통일 (단어 경계 고려)
    ("lim", "im"),  # Lim→Im
    ("ahn", "an"),  # Ahn→An
    ("kang","gang"),# Kang→Gang (강씨)
    ("choe","choi"),# Choe→Choi
    # 기타
    ("ph",  "p"),
    ("rh",  "r"),
]

_FUZZY_THRESHOLD = 0.84  # difflib 유사도 임계값


def _normalize(name: str) -> str:
    """기본 정규화: 소문자, 악센트 제거, 비알파벳 제거."""
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _normalize_ko(name: str) -> str:
    """한국어 로마자 변형까지 통일한 정규화."""
    s = _normalize(name)
    for old, new in _KO_ROMAN_SUBS:
        s = s.replace(old, new)
    return s


def _reversed_name(tm_name: str) -> str:
    """'Given-name Surname' → 'Surname Given-name' 변환."""
    parts = tm_name.split()
    if len(parts) >= 2:
        return " ".join(parts[-1:] + parts[:-1])
    return tm_name


def build_name_index(players: list[dict]) -> tuple[dict, dict]:
    """
    name_en / wiki_slug 기준 인덱스 두 개 생성:
      idx_base : _normalize() 기반
      idx_ko   : _normalize_ko() 기반 (로마자 변형 통일)
    """
    idx_base: dict[str, list[dict]] = {}
    idx_ko:   dict[str, list[dict]] = {}
    for p in players:
        for field in ("name_en", "wiki_slug"):
            raw = (p.get(field) or "").replace("_", " ")
            if not raw:
                continue
            for idx, norm_fn in ((idx_base, _normalize), (idx_ko, _normalize_ko)):
                key = norm_fn(raw)
                if key:
                    idx.setdefault(key, []).append(p)
    return idx_base, idx_ko


def _pick(candidates: list[dict], team_ko: str) -> dict:
    """후보 목록에서 팀 일치 선수 우선 반환."""
    for c in candidates:
        if c.get("team_short") == team_ko:
            return c
    return candidates[0]


def match_player(
    tm_name: str,
    team_ko: str,
    idx_base: dict[str, list[dict]],
    idx_ko:   dict[str, list[dict]],
    all_players: list[dict],
) -> dict | None:
    """
    TM 이름 → player_profiles.json 선수 매칭. 단계별 시도:

    1. 기본 정규화 exact match
    2. 역순 이름(Given-Surname→Surname-Given) exact match
    3. 한국어 로마자 정규화 exact match
    4. 한국어 로마자 정규화 + 역순 exact match
    5. difflib 유사도 매칭 (임계값 0.84)
    """
    rev_name = _reversed_name(tm_name)

    # 단계 1~4: 인덱스 룩업
    for name_variant in (tm_name, rev_name):
        for norm_fn, idx in (
            (_normalize,    idx_base),
            (_normalize_ko, idx_ko),
        ):
            key = norm_fn(name_variant)
            cands = idx.get(key)
            if cands:
                return _pick(cands, team_ko)

    # 단계 5: difflib 퍼지 매칭
    tm_key = _normalize_ko(tm_name)
    tm_rev_key = _normalize_ko(rev_name)
    best: dict | None = None
    best_ratio = _FUZZY_THRESHOLD

    for p in all_players:
        for field in ("name_en", "wiki_slug"):
            raw = (p.get(field) or "").replace("_", " ")
            if not raw:
                continue
            p_key = _normalize_ko(raw)
            for query_key in (tm_key, tm_rev_key):
                ratio = SequenceMatcher(None, query_key, p_key).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best = p

    return best


# ── 메인 ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="첫 팀만 테스트")
    parser.add_argument("--team",    type=str,   default=None, help="특정 팀 short_name만 처리")
    args = parser.parse_args()

    data    = json.loads(PROFILES.read_text(encoding="utf-8"))
    players = data["players"]

    idx_base, idx_ko = build_name_index(players)
    logger.info(f"인덱스 구축: base {len(idx_base)}개 / ko {len(idx_ko)}개 키 / {len(players)}명")

    teams = K1_TM_TEAMS
    if args.dry_run:
        teams = teams[:1]
        logger.info("[DRY-RUN] 첫 팀만 처리")
    if args.team:
        teams = [t for t in teams if t["name_ko"] == args.team]
        if not teams:
            logger.error(f"팀 없음: {args.team}")
            return

    birth_added  = 0
    height_added = 0
    total_matched = 0

    for team in teams:
        logger.info(f"▶ {team['name_ko']} (TM ID: {team['tm_id']})")
        squad = fetch_squad(team)
        time.sleep(DELAY)

        for p_tm in squad:
            profile = match_player(p_tm["name_tm"], team["name_ko"], idx_base, idx_ko, players)
            if not profile:
                logger.debug(f"  매칭 실패: {p_tm['name_tm']} ({team['name_ko']})")
                continue

            need_birth  = not profile.get("birth_date")
            need_height = not profile.get("height_cm")
            if not need_birth and not need_height:
                continue  # 이미 완비

            info = fetch_player_info(p_tm["tm_slug"], p_tm["tm_id"])
            time.sleep(DELAY)

            if not info:
                continue

            total_matched += 1
            if need_birth and info.get("birth_date"):
                profile["birth_date"] = info["birth_date"]
                profile["age"]        = info["age"]
                birth_added += 1
                logger.debug(f"  ✓ {p_tm['name_tm']} → 생년월일 {info['birth_date']}")
            if need_height and info.get("height_cm"):
                profile["height_cm"] = info["height_cm"]
                height_added += 1
                logger.debug(f"  ✓ {p_tm['name_tm']} → 신장 {info['height_cm']}cm")
            if info.get("birth_date") or info.get("height_cm"):
                profile["enrich_source"] = "transfermarkt"

        logger.info(
            f"  → 누계: 생년월일 +{birth_added} / 신장 +{height_added}"
        )
        time.sleep(DELAY)

    # 최종 통계
    total_birth  = sum(1 for p in players if p.get("birth_date"))
    total_height = sum(1 for p in players if p.get("height_cm"))
    logger.info(
        f"완료 — 생년월일: {total_birth}/{len(players)} | "
        f"신장: {total_height}/{len(players)} | "
        f"이번 추가: 생년월일 +{birth_added} / 신장 +{height_added}"
    )

    if not args.dry_run:
        data["enriched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        PROFILES.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.success(f"저장 완료: {PROFILES}")
    else:
        logger.info("[DRY-RUN] 저장 생략")
        needs = [p for p in players if not p.get("birth_date") or not p.get("height_cm")]
        enriched = [p for p in needs if p.get("enrich_source") == "transfermarkt"]
        logger.info(f"샘플 (첫 5명):")
        for p in enriched[:5]:
            name = (p.get("name_en") or "").encode("ascii", "replace").decode()
            print(f"  {name:30s} | {p.get('birth_date')} | {p.get('height_cm')}cm")


if __name__ == "__main__":
    main()
