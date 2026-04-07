"""
Wikidata 기반 선수 프로필 보강 스크립트.

접근 방법:
  1. wiki_slug → Wikipedia pageprops API → Wikidata QID
  2. QID 50개씩 묶어 Wikidata wbgetentities API 호출
  3. P569(생년월일), P2048(신장) 추출 → player_profiles.json 업데이트

기존 enrich_profiles.py (Wikipedia 인포박스 파싱)보다
  - 구조화된 데이터라 파싱 오류 없음
  - 50개 배치 요청으로 속도 빠름
  - 429 rate limit 위험 낮음

사용법:
  python enrich_wikidata.py           # 전체 보강
  python enrich_wikidata.py --dry-run # 처음 20명만 테스트
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from loguru import logger

sys.stderr.reconfigure(encoding="utf-8")
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | {level} | {message}")

BASE_DIR = Path(__file__).parent
PROFILES = BASE_DIR / "data" / "processed" / "players" / "player_profiles.json"
HEADERS  = {"User-Agent": "KLeagueWikidataEnricher/1.0 (research; contact@example.com)"}

WP_API  = "https://en.wikipedia.org/w/api.php"
WD_API  = "https://www.wikidata.org/w/api.php"

BATCH   = 50   # Wikidata API 최대 한 번에 처리 가능 엔티티 수


# ── Step 1: wiki_slug → Wikidata QID ──────────────────────────────────

def fetch_qids(slugs: list[str]) -> dict[str, str]:
    """
    Wikipedia 페이지 제목 리스트 → {slug: QID} 매핑 반환.
    한 번에 최대 50개 처리.
    """
    result: dict[str, str] = {}
    for i in range(0, len(slugs), BATCH):
        chunk = slugs[i: i + BATCH]
        try:
            r = requests.get(WP_API, params={
                "action": "query",
                "titles": "|".join(chunk),
                "prop":   "pageprops",
                "ppprop": "wikibase_item",
                "format": "json",
                "formatversion": "2",
                "redirects": "1",
            }, headers=HEADERS, timeout=15)
            if not r.ok:
                logger.warning(f"Wikipedia pageprops HTTP {r.status_code} (batch {i})")
                time.sleep(3)
                continue
            data = r.json()
            # redirects 정규화 맵 (redirect → target)
            norm: dict[str, str] = {}
            for red in data.get("query", {}).get("redirects", []):
                norm[red["from"].replace(" ", "_")] = red["to"].replace(" ", "_")

            for page in data.get("query", {}).get("pages", []):
                if page.get("missing"):
                    continue
                qid = page.get("pageprops", {}).get("wikibase_item")
                if not qid:
                    continue
                title = page["title"].replace(" ", "_")
                # 원래 slug 찾기 (redirect였을 수도 있으므로 역방향 매핑)
                # 가장 단순한 방법: chunk 내 슬러그와 title 비교
                for slug in chunk:
                    slug_norm = slug.replace("_", " ")
                    if page["title"] == slug_norm or page["title"] == slug:
                        result[slug] = qid
                        break
                else:
                    # redirect를 통해 매핑
                    for orig_slug, target in norm.items():
                        if target.replace(" ", "_") == title:
                            if orig_slug in chunk:
                                result[orig_slug] = qid
        except Exception as e:
            logger.debug(f"fetch_qids 실패 (batch {i}): {e}")
        time.sleep(1.0)
    return result


# ── Step 2: QID → 생년월일·신장 ────────────────────────────────────────

def fetch_wikidata_entities(qids: list[str]) -> dict[str, dict]:
    """
    QID 리스트 → {QID: {"birth_date": "YYYY-MM-DD", "height_cm": int}} 매핑.
    """
    result: dict[str, dict] = {}
    for i in range(0, len(qids), BATCH):
        chunk = qids[i: i + BATCH]
        try:
            r = requests.get(WD_API, params={
                "action": "wbgetentities",
                "ids":    "|".join(chunk),
                "props":  "claims",
                "format": "json",
            }, headers=HEADERS, timeout=20)
            if not r.ok:
                logger.warning(f"Wikidata API HTTP {r.status_code} (batch {i})")
                time.sleep(5)
                continue
            data = r.json()
            for qid, entity in data.get("entities", {}).items():
                if entity.get("missing") == "":
                    continue
                claims = entity.get("claims", {})
                info: dict = {}

                # P569 = date of birth
                p569 = claims.get("P569", [])
                if p569:
                    val = p569[0].get("mainsnak", {}).get("datavalue", {}).get("value", {})
                    raw_time = val.get("time", "")  # "+1990-05-14T00:00:00Z"
                    if raw_time:
                        # "+YYYY-MM-DDT..." 형식 파싱
                        try:
                            ts = raw_time.lstrip("+").split("T")[0]
                            parts = ts.split("-")
                            if len(parts) == 3 and all(parts):
                                y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
                                if y > 0 and 1 <= mo <= 12 and 1 <= d <= 31:
                                    info["birth_date"] = f"{y:04d}-{mo:02d}-{d:02d}"
                                    info["age"] = datetime.now().year - y
                        except Exception:
                            pass

                # P2048 = height (cm)
                p2048 = claims.get("P2048", [])
                if p2048:
                    val = p2048[0].get("mainsnak", {}).get("datavalue", {}).get("value", {})
                    amount = val.get("amount")   # "+183" 또는 "1.83"
                    unit   = val.get("unit", "")  # URL 형태: "http://www.wikidata.org/entity/Q11573" = metre
                    if amount:
                        try:
                            v = float(amount)
                            # 단위가 metre(Q11573)이면 cm로 변환
                            if "Q11573" in unit:
                                v = round(v * 100)
                            v = int(v)
                            if 140 <= v <= 220:  # 축구 선수 신장 범위 검증
                                info["height_cm"] = v
                        except Exception:
                            pass

                if info:
                    result[qid] = info
        except Exception as e:
            logger.debug(f"fetch_wikidata_entities 실패 (batch {i}): {e}")
        time.sleep(1.0)
    return result


# ── 메인 ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="처음 20명만 테스트")
    args = parser.parse_args()

    data    = json.loads(PROFILES.read_text(encoding="utf-8"))
    players = data["players"]

    # 보강 대상: birth_date 또는 height_cm 가 없고, wiki_slug가 있는 선수
    targets = [
        p for p in players
        if p.get("wiki_slug") and (not p.get("birth_date") or not p.get("height_cm"))
    ]
    logger.info(f"보강 대상: {len(targets)}명 / 전체 {len(players)}명")

    if args.dry_run:
        targets = targets[:20]
        logger.info("[DRY-RUN] 처음 20명만 처리")

    # ── Step 1: wiki_slug → QID ──
    slugs    = [p["wiki_slug"] for p in targets]
    logger.info(f"Step 1: {len(slugs)}개 slug → Wikipedia pageprops 조회")
    slug_qid = fetch_qids(slugs)
    logger.info(f"  QID 획득: {len(slug_qid)}개")

    # QID → player 역방향 맵
    qid_to_players: dict[str, list[dict]] = {}
    for p in targets:
        qid = slug_qid.get(p["wiki_slug"])
        if qid:
            qid_to_players.setdefault(qid, []).append(p)

    # ── Step 2: QID → Wikidata 엔티티 ──
    all_qids = list(qid_to_players.keys())
    logger.info(f"Step 2: {len(all_qids)}개 QID → Wikidata 엔티티 조회")
    qid_info = fetch_wikidata_entities(all_qids)
    logger.info(f"  데이터 획득: {len(qid_info)}개 QID")

    # ── Step 3: 선수 프로필 업데이트 ──
    birth_added  = 0
    height_added = 0

    for qid, info in qid_info.items():
        for p in qid_to_players.get(qid, []):
            had_birth  = bool(p.get("birth_date"))
            had_height = bool(p.get("height_cm"))

            if not had_birth and info.get("birth_date"):
                p["birth_date"] = info["birth_date"]
                p["age"]        = info["age"]
                birth_added += 1
            if not had_height and info.get("height_cm"):
                p["height_cm"] = info["height_cm"]
                height_added += 1

            if (not had_birth and p.get("birth_date")) or (not had_height and p.get("height_cm")):
                p["enrich_source"] = "wikidata"

    # ── 결과 ──
    total_birth  = sum(1 for p in players if p.get("birth_date"))
    total_height = sum(1 for p in players if p.get("height_cm"))
    logger.info(
        f"완료 — 생년월일 +{birth_added} / 신장 +{height_added} | "
        f"전체: 생년월일 {total_birth}/{len(players)} | 신장 {total_height}/{len(players)}"
    )

    if args.dry_run:
        logger.info("[DRY-RUN] 샘플 결과:")
        shown = [p for p in targets if p.get("enrich_source") == "wikidata"][:10]
        for p in shown:
            line = f"  {p['name_en']:30s} | 생년월일: {p.get('birth_date')} | 신장: {p.get('height_cm')}cm"
            sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))
    else:
        data["enriched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        PROFILES.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.success(f"저장 완료: {PROFILES}")


if __name__ == "__main__":
    main()
