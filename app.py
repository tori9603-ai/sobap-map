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

# 검색 엔진 로직 유지 (Nominatim + Kakao 하이브리드)
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
    
    with st.expander("➕ 신규 점주 등록"):
        new_name = st.text_input("새 점주 성함")
        if st.button("점주 영구 등록"):
            if new_name:
                payload = {"action": "add", "owner": new_name, "address": "신규등록", "lat": 0, "lon": 0}
                requests.post(API_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
                st.success("등록 완료!"); st.cache_data.clear(); time.sleep(1); st.rerun()

    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in df['owner'] if name.strip() and name != 'owner'])))
    st.write("---")
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    st.markdown("---")
    st.header("2️⃣ 영업권 구역 선점")
    search_addr = st.text_input("아파트명 또는 주소 입력")
    
    if st.button("🔍 위치 찾기", use_container_width=True):
        if search_addr:
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

    # ⭐ [기능 수정] 선점하기 버튼 및 500m 반경 체크
    if st.session_state.temp_loc and selected_owner != "선택":
        st.write("---")
        t = st.session_state.temp_loc
        if st.button("🚩 해당 주소 선점하기 (500m)", use_container_width=True):
            is_overlap = False
            # 모든 영업권을 500m 기준으로 체크
            new_radius = 500 
            new_pos = (t['lat'], t['lon'])

            for _, row in df.iterrows():
                if row['lat'] != 0:
                    if str(row['owner']).split('|')[0].strip() == selected_owner: continue
                    dist = geodesic(new_pos, (row['lat'], row['lon'])).meters
                    # 기존 영업권도 모두 500m 반경 보호구역으로 간주
                    if dist < 500: 
                        is_overlap = True; break
            
            if is_overlap:
                st.error("이미 500m 이내에 선점된 구역이 있습니다.")
            else:
                place_name = t['display_name'].split(']')[-1].strip()
                save_val = f"{selected_owner} | {place_name}"
                payload = {"action": "add", "owner": save_val, "address": t['display_name'], "lat": t['lat'], "lon": t['lon']}
                requests.post(API_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
                st.success(f"✅ 500m 영업권 선점 완료!")
                st.session_state.temp_loc = None
                st.cache_data.clear(); time.sleep(1); st.rerun()

# --- 메인 지도 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")

# 지도 생성
m = folium.Map(location=st.session_state.map_center, zoom_start=15)

# 1. 기존 점주 데이터 표시 (500m 원형 포함)
for _, row in df.iterrows():
    if row['lat'] != 0:
        owner_name = str(row['owner']).split('|')[0].strip()
        color = "red" if owner_name == selected_owner else "blue"
        # 마커 추가
        folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
        # ⭐ 500m 반경 원 추가
        folium.Circle(
            location=[row['lat'], row['lon']],
            radius=500,
            color=color,
            fill=True,
            fill_opacity=0.1
        ).add_to(m)

# 2. 현재 작업 중인 임시 위치 표시 (초록색 별 + 500m 점선 원)
if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    # ⭐ 500m 가이드 라인 원 추가
    folium.Circle(
        location=[t['lat'], t['lon']],
        radius=500,
        color="green",
        fill=False,
        dash_array='5, 5'
    ).add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
