import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정 및 디자인 (사장님 디자인 절대 유지)
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

# ⚠️ 사장님 고유 정보 유지
API_URL = "https://script.google.com/macros/s/AKfycbw4MGFNridXvxj906TWMp0v37lcB-aAl-EWwC2ellpS98Kgm5k5jda4zRyaIHFDpKtB/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79" 

# 검색 엔진 로직 유지
def get_location_alternative(query):
    results = []
    try:
        geolocator = Nominatim(user_agent="sojunghan_bapsang_manager")
        locations = geolocator.geocode(query, exactly_one=False, limit=5, country_codes='kr')
        if locations:
            for loc in locations:
                results.append({"display_name": f"[추천] {loc.address}", "lat": loc.latitude, "lon": loc.longitude})
    except: pass
    
    if not results:
        headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        try:
            res = requests.get(f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}", headers=headers, timeout=3).json()
            for d in res.get('documents', []):
                results.append({"display_name": f"[{d.get('place_name')}] {d['address_name']}", "lat": float(d['y']), "lon": float(d['x'])})
        except: pass
    return results

@st.cache_data(ttl=5)
def get_data_cached(api_url):
    try:
        response = requests.get(api_url, allow_redirects=True)
        data = response.json()
        df = pd.DataFrame(data[1:], columns=data[0])
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

df = get_data_cached(API_URL)

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None

# --- 사이드바 ---
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    st.header("👤 점주 관리")
    
    # 1. 신규 점주 등록
    with st.expander("➕ 신규 점주 등록"):
        new_name = st.text_input("새 점주 성함")
        if st.button("점주 영구 등록"):
            if new_name:
                payload = {"action": "add", "owner": new_name, "address": "신규등록", "lat": 0, "lon": 0}
                requests.post(API_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
                st.success("등록 완료!"); st.cache_data.clear(); time.sleep(1); st.rerun()

    # ⭐ [수정] 점주 리스트 표시 삭제 및 데이터 준비
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in df['owner'] if name.strip() and name != 'owner'])))

    st.write("---")
    # 등록된 리스트 없이 바로 선택창 노출
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    if selected_owner != "선택":
        target_data = df[(df['owner'].str.contains(selected_owner, na=False)) & (df['lat'] != 0)]
        if not target_data.empty:
            if st.button(f"📍 {selected_owner}님 위치로 이동"):
                st.session_state.map_center = [target_data.iloc[0]['lat'], target_data.iloc[0]['lon']]
                st.rerun()

    st.markdown("---")
    st.header("2️⃣ 영업권 구역 선점")
    search_addr = st.text_input("아파트명 또는 주소 입력")
    
    if st.button("🔍 위치 찾기", use_container_width=True):
        results = get_location_alternative(search_addr)
        if results:
            st.session_state.search_results = results
            st.session_state.map_center = [results[0]['lat'], results[0]['lon']]
            st.rerun()
        else: st.error("주소를 찾을 수 없습니다.")

    if st.session_state.search_results:
        res_options = { r['display_name']: r for r in st.session_state.search_results }
        sel = st.selectbox("정확한 위치를 선택하세요", list(res_options.keys()))
        if st.button("📍 위치 확인"):
            st.session_state.temp_loc = res_options[sel]
            st.session_state.map_center = [st.session_state.temp_loc['lat'], st.session_state.temp_loc['lon']]
            st.rerun()

# --- 메인 지도 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")
m = folium.Map(location=st.session_state.map_center, zoom_start=15)

for _, row in df.iterrows():
    if row['lat'] != 0:
        folium.Marker([row['lat'], row['lon']], popup=str(row['owner'])).add_to(m)

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
