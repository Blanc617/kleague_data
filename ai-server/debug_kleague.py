"""
kleague.com 경기 일정 API 파라미터 조사용 스크립트.
확인 후 삭제해도 됩니다.
"""

import json
import re
import requests

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.kleague.com/schedule.do",
    "X-Requested-With": "XMLHttpRequest",
})

# schedule.do HTML에서 getScheduleList.do ajax 호출 파라미터 추출
print("[1] schedule.do HTML에서 파라미터 추출")
resp = session.get("https://www.kleague.com/schedule.do?leagueId=1", timeout=10)
html = resp.text

# getScheduleList.do 호출 주변 200자 추출
idx = html.find("getScheduleList.do")
if idx != -1:
    snippet = html[max(0, idx-300):idx+500]
    print(snippet)
else:
    print("getScheduleList.do 미발견")

# 여러 파라미터 조합 시도
print("\n[2] 파라미터 조합 테스트")
test_cases = [
    {"leagueId": "1", "year": "2025", "month": "03"},
    {"leagueId": "1", "year": "2025", "month": ""},
    {"leagueId": "1", "seasonYear": "2025"},
    {"leagueId": "1", "year": "2025"},
    {"leagueId": "1", "year": "2026", "month": "03"},
    {"leagueId": "1", "year": "2026"},
]

for params in test_cases:
    try:
        resp = session.post(
            "https://www.kleague.com/getScheduleList.do",
            json=params,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        data = resp.json()
        code = data.get("resultCode", "?")
        msg = data.get("resultMsg", "")
        count = 0
        if code == "200":
            inner = data.get("data", {})
            for key, val in inner.items():
                if isinstance(val, list):
                    count = len(val)
                    break
        print(f"  params={params} → {code} {msg} | 데이터: {count}건")
    except Exception as e:
        print(f"  params={params} → ERROR: {e}")

# 실제 성공한 응답의 첫 번째 항목 구조 확인
print("\n[3] 실제 응답 데이터 구조 확인 (2025년 3월)")
resp = session.post(
    "https://www.kleague.com/getScheduleList.do",
    json={"leagueId": "1", "year": "2025", "month": "03"},
    headers={"Content-Type": "application/json"},
    timeout=10,
)
data = resp.json()
inner = data.get("data", {})
print(f"data 키 목록: {list(inner.keys())}")
for key, val in inner.items():
    if isinstance(val, list) and val:
        print(f"\n'{key}' 첫 번째 항목:")
        print(json.dumps(val[0], ensure_ascii=False, indent=2))
