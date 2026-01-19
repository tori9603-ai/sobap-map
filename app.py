import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정 및 디자인 (사장님 디자인 100% 유지)
st.set_page_config(page_title="소중한밥상 통합 관제 시스템", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
        [data-testid="stSidebar"] { background-color: #FFF0F0; }
        [data-testid="stSidebarCollapsedControl"] svg { display: none !important; }
        [data-testid="stSidebarCollapsedControl"] {
            background-color: #FF4B4B !important; color: white !important;
            border-radius: 0 15px 15px 0 !important; width: 160px !important; height: 65px !important;
            display: flex !important; align-items: center !important; justify-content: center !important;
            position: fixed !important; left: 0 !important; top: 20px !important;
            box-shadow: 5px 5px 15px rgba(0,0,0,0.5) !important; z-index: 1000000 !important; cursor: pointer !important;
        }
        [data-testid="stSidebarCollapsedControl"]::after {
            content: "🆑 클릭해서 메뉴열기" !important;
            font-weight: 900 !important; color: white !important; font-size: 17px !important; white-space: nowrap !important;
        }
    </style>
    """, unsafe_allow_html=True)

# ⚠️ [수정완료] 사장님이 새로 배포하신 구글 앱스 스크립트 URL 반영
API_URL = "https://script.google.com/macros/s/AKfycbzwD6llL7fipt7d-SVRXlxftJet0HV5oVQYPAQuAsCxg2i9idA6ZcEq_edzI55a2gH1/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79" 

# --- 데이터 로드 함수 (최적화) ---
def fetch_data(api_url):
    try:
        # allow_redirects=True 설정을 통해 구글 서버의 응답을 끝까지 추적합니다.
        response = requests.get(api_url, allow_redirects=True, timeout=10)
        data = response.json()
        df = pd.DataFrame(data[1:], columns=data[0])
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

# 세션 상태 초기화 (데이터 캐싱)
if 'df' not in st.session_state: st.session_state.df = fetch_data(API_URL)
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'prev_owner' not in st.session_state: st.session_state.prev_owner = "선택"

# 지명 간소화 로직
def simplify_name(full_name):
    clean = full_name.replace("[지점]", "").replace("[동네]", "").strip()
    if "," in clean: clean = clean.split(",")[0].strip()
    return clean

# 검색 엔진 (Nominatim + Kakao 하이브리드)
def get_location_alternative(query):
    results = []
    try:
        geolocator = Nominatim(user_agent="sojunghan_bapsang_manager")
        locations = geolocator.geocode(query, exactly_one=False, limit=5, country_codes='kr')
        if locations:
            for loc in locations:
                is_area = any(x in query for x in ["동", "읍", "면", "리"])
                results.append({"display_name": f"{'[동네] ' if is_area else '[지점] '} {loc.address}", "lat": loc.latitude, "lon": loc.longitude, "is_area": is_area})
    except: pass
    if not results:
        headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        try:
            res = requests.get(f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}", headers=headers, timeout=3).json()
            for d in res.get('documents', []):
                is_area = any(x in query for x in ["동", "읍", "면", "리"])
                results.append({"display_name": f"{'[동네] ' if is_area else '[지점] '} {d['place_name']} ({d['address_name']})", "lat": float(d['y']), "lon": float(d['x']), "is_area": is_area})
        except: pass
    return results

# --- 사이드바 ---
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    if st.button("🔄 전체 데이터 새로고침", use_container_width=True):
        st.session_state.df = fetch_data(API_URL)
        st.rerun()

    st.header("👤 점주 관리")
    with st.expander("➕ 신규 점주 등록"):
        new_name = st.text_input("새 점주 성함")
        if st.button("점주 영구 등록"):
            if new_name:
                requests.post(API_URL, data=json.dumps({"action": "add", "owner": new_name, "address": "신규등록", "lat": 0, "lon": 0}))
                st.session_state.df = fetch_data(API_URL)
                st.success("등록 완료!"); time.sleep(1); st.rerun()

    # 등록된 점주 목록 추출
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in st.session_state.df['owner'] if name.strip() and name != 'owner'])))
    st.write("---")
    
    # 점주 선택 및 자동 이동
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    if selected_owner != st.session_state.prev_owner:
        if selected_owner != "선택":
            owner_data = st.session_state.df[st.session_state.df['owner'].str.contains(f"^{selected_owner}\s*\|", na=False)]
            valid_coords = owner_data[owner_data['lat'] != 0]
            if not valid_coords.empty:
                st.session_state.map_center = [valid_coords.iloc[0]['lat'], valid_coords.iloc[0]['lon']]
        st.session_state.prev_owner = selected_owner
        st.rerun()

    if selected_owner != "선택":
        st.markdown("---")
        st.header("📍 선점 내역")
        owner_data = st.session_state.df[st.session_state.df['owner'].str.contains(f"^{selected_owner}\s*\|", na=False)]
        
        if not owner_data.empty:
            # 그룹형 리스트 표시 (개별지점 100m / 동네구역 1km)
            for title, pattern, icon in [("📍 개별 지점 (100m)", "^((?!\[동네\]).)*$", "🏠"), ("🏘️ 동네 구역 (1km)", "\[동네\]", "🏘️")]:
                subset = owner_data[owner_data['owner'].str.contains(pattern, na=True)]
                if not subset.empty:
                    st.markdown(f"##### {title}")
                    for idx, row in subset.iterrows():
                        name = simplify_name(row['owner'].split('|')[-1])
                        c1, c2 = st.columns([4, 1])
                        with c1:
                            if st.button(f"{icon} {name}", key=f"go_{idx}", use_container_width=True):
                                st.session_state.map_center = [row['lat'], row['lon']]; st.rerun()
                        with c2:
                            # ❌ 삭제 버튼 (새 API URL로 명령 전송)
                            if st.button("❌", key=f"del_{idx}"):
                                requests.post(API_URL, data=json.dumps({"action": "delete", "row_index": int(idx) + 2}))
                                st.session_state.df = fetch_data(API_URL)
                                st.rerun()
        else: st.info("선점 내역이 없습니다.")

    st.markdown("---")
    st.header("2️⃣ 영업권 구역 선점")
    search_addr = st.text_input("아파트명 또는 주소 입력", key="s_box")
    if st.button("🔍 위치 찾기", use_container_width=True):
        res = get_location_alternative(search_addr)
        if res:
            st.session_state.search_results = res
            st.session_state.map_center = [res[0]['lat'], res[0]['lon']]; st.rerun()
        else: st.error("주소를 찾을 수 없습니다.")

    if st.session_state.search_results:
        res_opts = { r['display_name']: r for r in st.session_state.search_results }
        sel = st.selectbox("정확한 위치 선택", list(res_opts.keys()))
        if st.button("📍 위치 확인"):
            st.session_state.temp_loc = res_opts[sel]
            st.session_state.map_center = [st.session_state.temp_loc['lat'], st.session_state.temp_loc['lon']]; st.rerun()

    if st.session_state.temp_loc and selected_owner != "선택":
        t = st.session_state.temp_loc
        r = 1000 if t['is_area'] else 100
        if st.button(f"🚩 선점하기 ({r}m)", use_container_width=True):
            prefix = "[동네] " if t['is_area'] else "[지점] "
            payload = {"action": "add", "owner": f"{selected_owner} | {prefix}{simplify_name(t['display_name'])}", "address": t['display_name'], "lat": t['lat'], "lon": t['lon']}
            requests.post(API_URL, data=json.dumps(payload))
            st.session_state.df = fetch_data(API_URL)
            st.session_state.temp_loc = None; st.rerun()

# --- 메인 지도 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")



m = folium.Map(location=st.session_state.map_center, zoom_start=15)

# 선점된 구역 표시 (원형 반경 포함)
for _, row in st.session_state.df.iterrows():
    if row['lat'] != 0:
        owner = str(row['owner']).split('|')[0].strip()
        color = "red" if owner == selected_owner else "blue"
        rad = 1000 if "[동네]" in str(row['owner']) else 100
        folium.Marker([row['lat'], row['lon']], icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=rad, color=color, fill=True, fill_opacity=0.1).add_to(m)

# 검색 중인 위치 표시
if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=1000 if t['is_area'] else 100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
