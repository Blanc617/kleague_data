"""
K리그1·2 팀 메타데이터 상수.
모든 크롤러가 이 파일의 상수를 참조합니다.
"""

from dataclasses import dataclass, field


@dataclass
class TeamMeta:
    name_ko: str
    name_en: str
    short_name: str
    kleague_team_id: str
    transfermarkt_slug: str
    transfermarkt_id: str
    wikipedia_ko: str
    wikipedia_en: str
    founded: int
    stadium: str
    derby_rivals: list[str] = field(default_factory=list)
    # 2026 시즌 K리그2 확장 대응용 활성화 기간
    active_from: int = 2000
    active_until: int = 9999


@dataclass
class DerbyMeta:
    name: str
    team_a: str
    team_b: str
    wikipedia_ko: str
    wikipedia_en: str = ""
    active: bool = True  # 양팀이 같은 리그에 있을 때만 True


# ──────────────────────────────────────────
# K리그1 팀 (2026 시즌 기준, 12팀)
# ──────────────────────────────────────────
K1_TEAMS: list[TeamMeta] = [
    TeamMeta(
        name_ko="전북 현대 모터스 FC",
        name_en="Jeonbuk Hyundai Motors FC",
        short_name="전북",
        kleague_team_id="K05",
        transfermarkt_slug="jeonbuk-hyundai-motors",
        transfermarkt_id="6502",
        wikipedia_ko="전북_현대_모터스_FC",
        wikipedia_en="Jeonbuk_Hyundai_Motors_FC",
        founded=1994,
        stadium="전주월드컵경기장",
        derby_rivals=["울산 HD FC"],
    ),
    TeamMeta(
        name_ko="울산 HD FC",
        name_en="Ulsan HD FC",
        short_name="울산",
        kleague_team_id="K01",
        transfermarkt_slug="ulsan-hyundai",
        transfermarkt_id="3535",
        wikipedia_ko="울산_HD_FC",
        wikipedia_en="Ulsan_HD_FC",
        founded=1983,
        stadium="문수축구경기장",
        derby_rivals=["전북 현대 모터스 FC"],
    ),
    TeamMeta(
        name_ko="FC 서울",
        name_en="FC Seoul",
        short_name="서울",
        kleague_team_id="K09",
        transfermarkt_slug="fc-seoul",
        transfermarkt_id="6500",
        wikipedia_ko="FC_서울",
        wikipedia_en="FC_Seoul",
        founded=1983,
        stadium="서울월드컵경기장",
        derby_rivals=["수원 삼성 블루윙즈"],
    ),
    TeamMeta(
        name_ko="포항 스틸러스",
        name_en="Pohang Steelers",
        short_name="포항",
        kleague_team_id="K03",
        transfermarkt_slug="pohang-steelers",
        transfermarkt_id="311",
        wikipedia_ko="포항_스틸러스",
        wikipedia_en="Pohang_Steelers",
        founded=1973,
        stadium="스틸야드",
    ),
    TeamMeta(
        name_ko="인천 유나이티드 FC",
        name_en="Incheon United FC",
        short_name="인천",
        kleague_team_id="K18",
        transfermarkt_slug="incheon-united",
        transfermarkt_id="2996",
        wikipedia_ko="인천_유나이티드_FC",
        wikipedia_en="Incheon_United_FC",
        founded=2003,
        stadium="인천축구전용경기장",
    ),
    TeamMeta(
        name_ko="수원 FC",
        name_en="Suwon FC",
        short_name="수원FC",
        kleague_team_id="K29",
        transfermarkt_slug="suwon-fc",
        transfermarkt_id="31622",
        wikipedia_ko="수원_FC",
        wikipedia_en="Suwon_FC",
        founded=2003,
        stadium="수원종합운동장",
    ),
    TeamMeta(
        name_ko="대전 하나 시티즌",
        name_en="Daejeon Hana Citizen",
        short_name="대전",
        kleague_team_id="K10",
        transfermarkt_slug="daejeon-hana-citizen",
        transfermarkt_id="6499",
        wikipedia_ko="대전_하나_시티즌",
        wikipedia_en="Daejeon_Hana_Citizen",
        founded=1997,
        stadium="대전월드컵경기장",
    ),
    TeamMeta(
        name_ko="광주 FC",
        name_en="Gwangju FC",
        short_name="광주",
        kleague_team_id="K22",
        transfermarkt_slug="gwangju-fc",
        transfermarkt_id="30925",
        wikipedia_ko="광주_FC",
        wikipedia_en="Gwangju_FC",
        founded=2010,
        stadium="광주축구전용구장",
    ),
    TeamMeta(
        name_ko="강원 FC",
        name_en="Gangwon FC",
        short_name="강원",
        kleague_team_id="K21",
        transfermarkt_slug="gangwon-fc",
        transfermarkt_id="21459",
        wikipedia_ko="강원_FC",
        wikipedia_en="Gangwon_FC",
        founded=2008,
        stadium="강릉종합운동장",
    ),
    TeamMeta(
        name_ko="제주 유나이티드 FC",
        name_en="Jeju United FC",
        short_name="제주",
        kleague_team_id="K04",
        transfermarkt_slug="jeju-united",
        transfermarkt_id="19684",
        wikipedia_ko="제주_유나이티드_FC",
        wikipedia_en="Jeju_United_FC",
        founded=1982,
        stadium="제주월드컵경기장",
    ),
    TeamMeta(
        name_ko="대구 FC",
        name_en="Daegu FC",
        short_name="대구",
        kleague_team_id="K17",
        transfermarkt_slug="daegu-fc",
        transfermarkt_id="6504",
        wikipedia_ko="대구_FC",
        wikipedia_en="Daegu_FC",
        founded=2002,
        stadium="DGB대구은행파크",
    ),
    TeamMeta(
        name_ko="전남 드래곤즈",
        name_en="Jeonnam Dragons",
        short_name="전남",
        kleague_team_id="K07",
        transfermarkt_slug="jeonnam-dragons",
        transfermarkt_id="6503",
        wikipedia_ko="전남_드래곤즈",
        wikipedia_en="Jeonnam_Dragons",
        founded=1994,
        stadium="광양축구전용구장",
    ),
]

# ──────────────────────────────────────────
# K리그2 팀 (2026 시즌 기준, 주요 팀)
# ──────────────────────────────────────────
K2_TEAMS: list[TeamMeta] = [
    TeamMeta(
        name_ko="수원 삼성 블루윙즈",
        name_en="Suwon Samsung Bluewings",
        short_name="수원삼성",
        kleague_team_id="K02",
        transfermarkt_slug="suwon-samsung-bluewings",
        transfermarkt_id="3296",
        wikipedia_ko="수원_삼성_블루윙즈",
        wikipedia_en="Suwon_Samsung_Bluewings",
        founded=1994,
        stadium="수원월드컵경기장",
        derby_rivals=["FC 서울"],
    ),
    TeamMeta(
        name_ko="성남 FC",
        name_en="Seongnam FC",
        short_name="성남",
        kleague_team_id="K08",
        transfermarkt_slug="seongnam-fc",
        transfermarkt_id="3292",
        wikipedia_ko="성남_FC",
        wikipedia_en="Seongnam_FC",
        founded=1989,
        stadium="탄천종합운동장",
    ),
    TeamMeta(
        name_ko="부산 아이파크",
        name_en="Busan IPark",
        short_name="부산",
        kleague_team_id="K06",
        transfermarkt_slug="busan-ipark",
        transfermarkt_id="3286",
        wikipedia_ko="부산_아이파크",
        wikipedia_en="Busan_IPark",
        founded=1983,
        stadium="구덕운동장",
    ),
    TeamMeta(
        name_ko="경남 FC",
        name_en="Gyeongnam FC",
        short_name="경남",
        kleague_team_id="K20",
        transfermarkt_slug="gyeongnam-fc",
        transfermarkt_id="12048",
        wikipedia_ko="경남_FC",
        wikipedia_en="Gyeongnam_FC",
        founded=2006,
        stadium="창원축구센터",
    ),
    TeamMeta(
        name_ko="안산 그리너스 FC",
        name_en="Ansan Greeners FC",
        short_name="안산",
        kleague_team_id="K32",
        transfermarkt_slug="ansan-greeners-fc",
        transfermarkt_id="20285",
        wikipedia_ko="안산_그리너스_FC",
        wikipedia_en="Ansan_Greeners_FC",
        founded=2017,
        stadium="안산와스타디움",
    ),
    TeamMeta(
        name_ko="충북 청주 FC",
        name_en="Chungbuk Cheongju FC",
        short_name="청주",
        kleague_team_id="K37",
        transfermarkt_slug="chungbuk-cheongju-fc",
        transfermarkt_id="85453",
        wikipedia_ko="충북_청주_FC",
        wikipedia_en="Chungbuk_Cheongju_FC",
        founded=2014,
        stadium="청주종합운동장",
    ),
    TeamMeta(
        name_ko="서울 이랜드 FC",
        name_en="Seoul E-Land FC",
        short_name="서울이랜드",
        kleague_team_id="K31",
        transfermarkt_slug="seoul-e-land-fc",
        transfermarkt_id="18485",
        wikipedia_ko="서울_이랜드_FC",
        wikipedia_en="Seoul_E-Land_FC",
        founded=2014,
        stadium="목동종합운동장",
    ),
    TeamMeta(
        name_ko="천안 시티 FC",
        name_en="Cheonan City FC",
        short_name="천안",
        kleague_team_id="K38",
        transfermarkt_slug="cheonan-city-fc",
        transfermarkt_id="85454",
        wikipedia_ko="천안_시티_FC",
        wikipedia_en="Cheonan_City_FC",
        founded=2020,
        stadium="천안종합운동장",
    ),
    TeamMeta(
        name_ko="충남 아산 FC",
        name_en="Chungnam Asan FC",
        short_name="아산",
        kleague_team_id="K34",
        transfermarkt_slug="chungnam-asan-fc",
        transfermarkt_id="65512",
        wikipedia_ko="충남_아산_FC",
        wikipedia_en="Chungnam_Asan_FC",
        founded=2017,
        stadium="이순신종합운동장",
    ),
    TeamMeta(
        name_ko="FC 안양",
        name_en="FC Anyang",
        short_name="안양",
        kleague_team_id="K27",
        transfermarkt_slug="fc-anyang",
        transfermarkt_id="18484",
        wikipedia_ko="FC_안양",
        wikipedia_en="FC_Anyang",
        founded=2013,
        stadium="안양종합운동장",
    ),
    TeamMeta(
        name_ko="부천 FC 1995",
        name_en="Bucheon FC 1995",
        short_name="부천",
        kleague_team_id="K26",
        transfermarkt_slug="bucheon-fc-1995",
        transfermarkt_id="18483",
        wikipedia_ko="부천_FC_1995",
        wikipedia_en="Bucheon_FC_1995",
        founded=2013,
        stadium="부천종합운동장",
    ),
    TeamMeta(
        name_ko="김포 FC",
        name_en="Gimpo FC",
        short_name="김포",
        kleague_team_id="K36",
        transfermarkt_slug="gimpo-fc",
        transfermarkt_id="85455",
        wikipedia_ko="김포_FC",
        wikipedia_en="Gimpo_FC",
        founded=2021,
        stadium="솔터스타디움",
    ),
    TeamMeta(
        name_ko="전북 현대 모터스 FC B",
        name_en="Jeonbuk Hyundai Motors FC B",
        short_name="전북B",
        kleague_team_id="K05",  # 전북B는 전북 ID 공유 (실제 확인 필요)
        transfermarkt_slug="jeonbuk-hyundai-motors-b",
        transfermarkt_id="85456",
        wikipedia_ko="전북_현대_모터스_FC",
        wikipedia_en="Jeonbuk_Hyundai_Motors_FC",
        founded=2022,
        stadium="전주월드컵경기장",
    ),
]

# ──────────────────────────────────────────
# 더비 매치 메타데이터
# ──────────────────────────────────────────
DERBY_FIXTURES: list[DerbyMeta] = [
    DerbyMeta(
        name="슈퍼매치",
        team_a="FC 서울",
        team_b="수원 삼성 블루윙즈",
        wikipedia_ko="슈퍼매치",
        wikipedia_en="Super_Match_(K_League)",
        active=False,  # 수원삼성이 K리그2로 강등 → 리그 간 더비로 전환
    ),
    DerbyMeta(
        name="클래식",
        team_a="전북 현대 모터스 FC",
        team_b="울산 HD FC",
        wikipedia_ko="전북_현대_모터스_FC",  # 더비 전적은 팀 문서 내 섹션에 포함
        wikipedia_en="Jeonbuk_Hyundai_Motors_vs_Ulsan_HD",
        active=True,
    ),
]

ALL_TEAMS: list[TeamMeta] = K1_TEAMS + K2_TEAMS
