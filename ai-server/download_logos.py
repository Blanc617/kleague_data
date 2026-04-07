import urllib.request
import os
import json
import time

# TheSportsDB free API
teams_query = {
    "전북": "Jeonbuk",
    "울산": "Ulsan",
    "포항": "Pohang",
    "서울": "FC Seoul",
    "수원FC": "Suwon FC",
    "제주": "Jeju",
    "인천": "Incheon",
    "광주": "Gwangju",
    "대구": "Daegu",
    "강원": "Gangwon",
    "김천": "Gimcheon",
    "대전": "Daejeon",
    "성남": "Seongnam",
    "수원": "Suwon",
    "전남": "Jeonnam",
    "부산": "Busan",
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

os.makedirs("../frontend/public/logos", exist_ok=True)
results = {}

for kr_name, en_name in teams_query.items():
    url = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={urllib.parse.quote(en_name)}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        teams = data.get('teams') or []
        # K-League팀 찾기
        found = None
        for t in teams:
            league = (t.get('strLeague') or '').lower()
            country = (t.get('strCountry') or '').lower()
            if 'korea' in country or 'k league' in league or 'k1' in league:
                found = t
                break
        if not found and teams:
            found = teams[0]
        
        if found:
            badge_url = found.get('strTeamBadge', '')
            if badge_url:
                # 로고 다운로드
                logo_url = badge_url + '/preview'
                req2 = urllib.request.Request(logo_url, headers=headers)
                with urllib.request.urlopen(req2, timeout=10) as r2:
                    img_data = r2.read()
                fname = f"../frontend/public/logos/{kr_name}.png"
                with open(fname, 'wb') as f:
                    f.write(img_data)
                results[kr_name] = f"/logos/{kr_name}.png"
                print(f"✅ {kr_name}: {badge_url}")
            else:
                print(f"⚠️  {kr_name}: 배지 URL 없음")
        else:
            print(f"❌ {kr_name}: 팀 없음")
    except Exception as e:
        print(f"❌ {kr_name}: {e}")
    time.sleep(0.3)

print("\n완료:", results)
