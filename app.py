import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.geocoders import Nominatim # 비상용 검색 엔진

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 관제 시스템 (비상모드)", layout="wide")

API_URL = "https://script.google.com/macros/s/AKfycbxDw8kU3K2LzcaM0zOStvwBdsZs98zyjNzQtgxJlRnZcjTCA70RUEQMLmg4lHTCb9uQ/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79"

def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df['owner'] = df['owner'].astype(str).str.strip()
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            df = df[~df['owner'].isin(['0', '', 'nan'])]
            return df
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
    except:
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

# 💡 [하이브리드 엔진] 카카오가 안되면 비상용 엔진으로 자동 전환
def get_location_smart(query):
    # 1단계: 카카오 API 시도
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    try:
        res = requests.get(f"https://dapi.kakao.com/v2/local/search/address.json?query={query}", headers=headers, timeout=5)
        if res.status_code == 200 and res.json().get('documents'):
            return res.json()['documents'], "✅ 카카오 정밀 검색 성공"
    except: pass

    # 2단계: 카카오 실패 시(승인 대기 중) 비상용 Nominatim 실행
    try:
        geolocator = Nominatim(user_agent=f"sobap_emergency_{int(time.time())}")
        # 한국 주소로 범위를 한정하여 검색 정확도 보강
        res = geolocator.geocode(f"{query}, 대한민국", exactly_one=False, timeout=10)
        if res:
            results = [{"address_name": r.address, "y": r.latitude, "x": r.longitude} for r in res]
            return results, "⚠️ 카카오 대기 중 (비상용 엔진 사용)"
    except: pass

    return [], "❓ 위치를 찾을 수 없습니다."

df = get_data()

# 세션 관리 (기존 유지)
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []

with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # 점주 등록 및 선택 (기존 동일)
    st.header("1️⃣ 점주 관리")
    with st.expander("➕ 신규 점주 등록"):
        add_name = st.text_input("이름 입력")
        if st.button("등록"):
            requests.post(API_URL, data=json.dumps({"action": "add", "owner": add_name, "address": "신규등록", "lat": 0, "lon": 0}))
            st.rerun()

    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in df['owner'] if name.strip()])))
    selected_owner = st.selectbox("점주 선택", ["선택"] + unique_owners)

    if selected_owner != "선택":
        st.markdown("---")
        st.header("2️⃣ 새 장소 검색")
        search_addr = st.text_input("주소 또는 아파트명")
        
        if st.button("🔍 위치 찾기"):
            results, status = get_location_smart(search_addr)
            if results:
                st.session_state.search_results = results
                st.info(status)
            else:
                st.warning(status)

        if st.session_state.search_results:
            res_options = { r['address_name']: r for r in st.session_state.search_results }
            sel_res_addr = st.selectbox("정확한 장소 선택", list(res_options.keys()))
            if st.button("📍 지도 위치 확인"):
                target = res_options[sel_res_addr]
                st.session_state.temp_loc = {"lat": float(target['y']), "lon": float(target['x']), "name": sel_res_addr.split(' ')[-1], "full_addr": sel_res_addr}
                st.session_state.map_center = [float(target['y']), float(target['x'])]
                st.rerun()

        if st.session_state.temp_loc:
            t = st.session_state.temp_loc
            if st.button(f"🚩 '{t['name']}' 최종 선점!"):
                save_val = f"{selected_owner} | {t['name']}"
                payload = {"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}
                requests.post(API_URL, data=json.dumps(payload))
                st.session_state.temp_loc = None
                st.rerun()

# --- 메인 지도 (기존 동일) ---
st.title("🗺️ 소중한밥상 실시간 관제 센터")
m = folium.Map(location=st.session_state.map_center, zoom_start=17)

for _, row in df.iterrows():
    if row['lat'] != 0:
        owner_label = str(row['owner']).split('|')[0].strip()
        color = "red" if owner_label == selected_owner else "blue"
        folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=100, color=color, fill=True, fill_opacity=0.15).add_to(m)

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)

st_folium(m, width="100%", height=800, key="main_map")
