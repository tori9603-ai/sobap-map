import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.distance import geodesic

# --- 1. 초기 설정 및 디자인 ---
st.set_page_config(page_title="소중한밥상 통합 관제 시스템", layout="wide", initial_sidebar_state="expanded")

# 카카오맵 승인 상태 변수 (승인 전: False / 승인 후: True)
# 나중에 승인이 완료되면 이 부분만 True로 바꾸시면 됩니다.
KAKAO_MAP_APPROVED = False 

st.markdown("""
    <style>
        [data-testid="stSidebar"] { background-color: #FFF0F0; }
        [data-testid="stSidebarCollapsedControl"] {
            background-color: #FF4B4B !important; color: white !important;
            border-radius: 0 15px 15px 0 !important; width: 160px !important; height: 65px !important;
            display: flex !important; align-items: center !important; justify-content: center !important;
            position: fixed !important; left: 0 !important; top: 20px !important;
            box-shadow: 5px 5px 15px rgba(0,0,0,0.5) !important; z-index: 1000000 !important; cursor: pointer !important;
        }
        [data-testid="stSidebarCollapsedControl"]::after {
            content: "🆑 클릭해서 메뉴열기" !important;
            font-weight: 900 !important; color: white !important; font-size: 17px !important;
        }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 고유 정보 및 데이터 로드 ---
API_URL = "https://script.google.com/macros/s/AKfycbw4MGFNridXvxj906TWMp0v37lcB-aAl-EWwC2ellpS98Kgm5k5jda4zRyaIHFDpKtB/exec"
KAKAO_REST_KEY = "57f491c105b67119ba2b79ec33cfff79" 
KAKAO_JS_KEY = "919179e81cdd52922456fbef112f964a"

@st.cache_data(ttl=5)
def get_data_cached(api_url):
    try:
        response = requests.get(api_url, allow_redirects=True, timeout=10)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            return df
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
    except: return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

def get_location_smart(query, api_key):
    headers = {"Authorization": f"KakaoAK {api_key}"}
    results = []
    try:
        # 주소 검색
        res = requests.get(f"https://dapi.kakao.com/v2/local/search/address.json?query={query}", headers=headers).json()
        for d in res.get('documents', []):
            results.append({"display_name": f"[주소] {d['address_name']}", "lat": float(d['y']), "lon": float(d['x']), "is_area": d.get('address_type') == 'REGION'})
        # 키워드(아파트 등) 검색
        res_kw = requests.get(f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}", headers=headers).json()
        for d in res_kw.get('documents', []):
            results.append({"display_name": f"[{d.get('category_group_name', '장소')}] {d['place_name']}", "lat": float(d['y']), "lon": float(d['x']), "is_area": False})
    except: pass
    return results

df = get_data_cached(API_URL)

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None

# --- 3. 사이드바 UI ---
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    st.header("👤 점주 관리")
    
    with st.expander("➕ 신규 점주 등록"):
        new_name = st.text_input("새 점주 성함")
        if st.button("점주 영구 등록", use_container_width=True):
            if new_name:
                payload = {"action": "add", "owner": new_name, "address": "신규등록", "lat": 0, "lon": 0}
                requests.post(API_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
                st.success("등록 완료!"); st.cache_data.clear(); time.sleep(1); st.rerun()

    st.markdown("---")
    st.header("2️⃣ 영업권 구역 선점")
    search_addr = st.text_input("아파트명 또는 주소 입력")
    
    if st.button("🔍 위치 찾기", use_container_width=True):
        res = get_location_smart(search_addr, KAKAO_REST_KEY)
        if res:
            st.session_state.search_results = res
            st.session_state.map_center = [res[0]['lat'], res[0]['lon']]
            st.rerun()
        else: st.error("결과가 없습니다.")

    if st.session_state.search_results:
        res_options = { r['display_name']: r for r in st.session_state.search_results }
        sel = st.selectbox("정확한 위치 선택", list(res_options.keys()))
        if st.button("📍 위치 확인"):
            st.session_state.temp_loc = res_options[sel]
            st.session_state.map_center = [st.session_state.temp_loc['lat'], st.session_state.temp_loc['lon']]
            st.rerun()

# --- 4. 메인 지도 영역 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")



if KAKAO_MAP_APPROVED:
    # --- 승인 후: 카카오맵 SDK 버전 ---
    kakao_html = f"""
    <div id="map" style="width:100%;height:800px;"></div>
    <script src="//dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JS_KEY}"></script>
    <script>
        var map = new kakao.maps.Map(document.getElementById('map'), {{
            center: new kakao.maps.LatLng({st.session_state.map_center[0]}, {st.session_state.map_center[1]}),
            level: 3
        }});
    </script>
    """
    st.components.v1.html(kakao_html, height=800)
else:
    # --- 승인 전: Folium 버전 ---
    m = folium.Map(location=st.session_state.map_center, zoom_start=16)
    
    # 기존 점주 표시
    for _, row in df.iterrows():
        if row['lat'] != 0:
            folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color="blue")).add_to(m)
            folium.Circle([row['lat'], row['lon']], radius=100, color="blue", fill=True, fill_opacity=0.1).add_to(m)
    
    # 검색 위치 표시
    if st.session_state.temp_loc:
        t = st.session_state.temp_loc
        folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
        
    st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
