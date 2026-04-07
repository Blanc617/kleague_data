"""
선수 프로필 보강 스크립트.

소스별 역할:
  1. 한국어 Wikipedia  → 내국인 선수 생년월일·신장·한국어 이름
  2. 영어 Wikipedia    → 외국인 선수 생년월일·신장 (기존에 없는 경우)
  3. Wikidata SPARQL  → 양쪽 모두 보완

입력:  data/processed/players/player_profiles.json
출력:  동일 파일 (in-place 업데이트)

사용법:
  python enrich_profiles.py           # 전체 보강
  python enrich_profiles.py --dry-run # 처음 10명만 테스트
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from datetime import datetime

import requests
from loguru import logger

sys.stderr.reconfigure(encoding="utf-8")
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | {level} | {message}")

BASE_DIR  = Path(__file__).parent
PROFILES  = BASE_DIR / "data" / "processed" / "players" / "player_profiles.json"
HEADERS   = {"User-Agent": "KLeagueProfileEnricher/1.0 (research)"}

# ── Wikipedia API ──────────────────────────────────────────────

def fetch_wiki(title: str, lang: str = "en") -> str:
    """Wikipedia 위키텍스트 가져오기. 빈 문자열 반환 시 문서 없음."""
    try:
        r = requests.get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params={
                "action": "query", "titles": title,
                "prop": "revisions", "rvprop": "content",
                "format": "json", "formatversion": "2", "redirects": "1",
            },
            headers=HEADERS, timeout=12,
        )
        if r.status_code == 429:
            logger.debug(f"429 rate limit: {title} ({lang})")
            time.sleep(10)
            return ""   # 이번 선수는 스킵, 다음 실행에서 재시도
        if not r.ok:
            return ""
        data = r.json()
        pages = data.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing"):
            return ""
        revs = pages[0].get("revisions", [])
        return revs[0].get("content", "") if revs else ""
    except Exception as e:
        logger.debug(f"fetch_wiki 실패: {title} ({lang}) | {e}")
        return ""


# ── 파싱 함수 ─────────────────────────────────────────────────

def parse_ko_wiki(content: str) -> dict:
    """한국어 Wikipedia 인포박스에서 생년월일·신장·이름 추출."""
    result: dict = {}

    # 생년월일: {{출생일과 나이|1991|9|25}} or {{출생일|1991|9|25}}
    bd = re.search(r'\{\{출생일(?:과 나이)?\s*\|(\d{4})\|(\d{1,2})\|(\d{1,2})', content)
    if bd:
        y, mo, d = bd.groups()
        result["birth_date"] = f"{y}-{int(mo):02d}-{int(d):02d}"
        result["age"] = datetime.now().year - int(y)

    # 신장/키: | 키 = 189 or | 신장 = 189
    ht = re.search(r'(?:키|신장)\s*=\s*(\d{3})', content)
    if ht:
        result["height_cm"] = int(ht.group(1))

    # 한국어 이름 (이름 필드)
    name_m = re.search(r'\|이름\s*=\s*([^\n|{}\[\]]+)', content)
    if name_m:
        result["name_ko"] = name_m.group(1).strip()

    return result


def parse_en_wiki(content: str) -> dict:
    """영어 Wikipedia 인포박스에서 생년월일·신장 추출."""
    result: dict = {}

    # 생년월일: {{birth date and age|1990|5|14}} or {{birth date|...}}
    bd = re.search(
        r'\{\{birth date(?:\s+and\s+age)?\s*\|(\d{4})\|(\d{1,2})\|(\d{1,2})',
        content, re.IGNORECASE,
    )
    if bd:
        y, mo, d = bd.groups()
        result["birth_date"] = f"{y}-{int(mo):02d}-{int(d):02d}"
        result["age"] = datetime.now().year - int(y)

    # 신장: {{convert|183|cm|...}} or | height_m = 1.83 or | height = 183
    ht = re.search(r'\{\{convert\|(\d{2,3})\|cm', content, re.IGNORECASE)
    if ht:
        result["height_cm"] = int(ht.group(1))
    else:
        ht2 = re.search(r'height_m\s*=\s*([\d.]+)', content, re.IGNORECASE)
        if ht2:
            result["height_cm"] = int(float(ht2.group(1)) * 100)
        else:
            ht3 = re.search(r'\|\s*height\s*=\s*(\d{3})', content, re.IGNORECASE)
            if ht3:
                result["height_cm"] = int(ht3.group(1))

    return result


# ── 선수별 보강 로직 ───────────────────────────────────────────

def needs_enrich(p: dict) -> bool:
    return not p.get("birth_date") or not p.get("height_cm")


def enrich_korean_player(p: dict) -> dict:
    """내국인 선수: ko.wikipedia 우선, 없으면 en.wikipedia."""
    name_ko = p.get("name_ko") or p.get("name_en", "")
    if not name_ko:
        return p

    # 1) 한국어 Wikipedia
    content = fetch_wiki(name_ko, lang="ko")
    if content:
        info = parse_ko_wiki(content)
        if info:
            p.update(info)
            p["enrich_source"] = "ko_wikipedia"
            return p

    # 2) 영어 Wikipedia (wiki_slug 있을 때)
    slug = p.get("wiki_slug")
    if slug:
        content_en = fetch_wiki(slug, lang="en")
        if content_en:
            info_en = parse_en_wiki(content_en)
            if info_en:
                p.update(info_en)
                p["enrich_source"] = "en_wikipedia"

    return p


def enrich_foreign_player(p: dict) -> dict:
    """외국인 선수: en.wikipedia wiki_slug 또는 name_en으로 시도."""
    # wiki_slug 우선
    slug = p.get("wiki_slug") or p.get("name_en", "")
    if not slug:
        return p

    content = fetch_wiki(slug, lang="en")
    if content:
        info = parse_en_wiki(content)
        if info:
            p.update(info)
            p["enrich_source"] = "en_wikipedia"

    return p


# ── 메인 ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="처음 10명만 테스트")
    args = parser.parse_args()

    data = json.loads(PROFILES.read_text(encoding="utf-8"))
    players = data["players"]

    targets = [p for p in players if needs_enrich(p)]
    logger.info(f"보강 대상: {len(targets)}명 / 전체 {len(players)}명")

    if args.dry_run:
        targets = targets[:10]
        logger.info("[DRY-RUN] 처음 10명만 처리")

    done = 0
    birth_added = 0
    height_added = 0

    for i, p in enumerate(targets, 1):
        had_birth  = bool(p.get("birth_date"))
        had_height = bool(p.get("height_cm"))

        if p["is_foreign"]:
            enrich_foreign_player(p)
        else:
            enrich_korean_player(p)

        if not had_birth  and p.get("birth_date"):  birth_added  += 1
        if not had_height and p.get("height_cm"):   height_added += 1

        done += 1
        if done % 20 == 0 or done == len(targets):
            logger.info(f"  진행: {done}/{len(targets)} | 생년월일+{birth_added} 신장+{height_added}")

        time.sleep(1.2)  # Wikipedia 요청 제한 준수

    # 결과 통계
    total_birth  = sum(1 for p in players if p.get("birth_date"))
    total_height = sum(1 for p in players if p.get("height_cm"))
    logger.info(f"완료 — 생년월일: {total_birth}/{len(players)} | 신장: {total_height}/{len(players)}")

    if not args.dry_run:
        data["enriched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        PROFILES.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.success(f"저장 완료: {PROFILES}")
    else:
        logger.info("[DRY-RUN] 샘플 결과:")
        for p in targets[:5]:
            print(f"  {p['name_en']} | 생년월일: {p.get('birth_date')} | 신장: {p.get('height_cm')}cm | 출처: {p.get('enrich_source','없음')}")


if __name__ == "__main__":
    main()
