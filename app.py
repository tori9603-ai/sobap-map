import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 통합 관제 시스템", layout="wide")

# 2. 구글 앱 스크립트 URL
API_URL = "https://script.google.com/macros/s/AKfycbxmLywtQIA-6Ay5_KczYt3zNIoGekzkdWD4I3X80PORIMw8gUNHMsZTvip8LXdopxTJ/exec"

def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
            df = df.dropna(subset=['lat', 'lon'])
            return df
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])
    except:
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])

df = get_data()

# --- 세션 상태 관리 ---
if 'map_center' not in st.session_state: st.session_state.map_center = [37.5665, 126.9780]
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = 11
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'last_selected' not in st.session_state: st.session_state.last_selected = None

# =========================================================
# 🍱 왼쪽 사이드바: 관리 프로세스
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # 1️⃣ 점주 선택
    st.header("1️⃣ 점주 선택")
    unique_owners = df['owner'].unique().tolist()
    selected_owner = st.selectbox("관리할 점주 선택", ["점주 선택"] + unique_owners)
    
    if selected_owner != "점주 선택" and selected_owner != st.session_state.last_selected:
        owner_df = df[df['owner'] == selected_owner]
        if not owner_df.empty:
            st.session_state.map_center = [owner_df['lat'].mean(), owner_df['lon'].mean()]
            st.session_state.map_zoom = 14
            st.session_state.last_selected = selected_owner
            st.rerun()

    st.markdown("---")

    if selected_owner != "점주 선택":
        # 2️⃣ 주소 검색 및 다중 결과 표시
        st.header("2️⃣ 주소 검색 및 선택")
        search_addr = st.text_input("검색할 주소 입력 (예: 롯데캐슬)")
        
        if st.button("🔍 주소 후보 찾기"):
            try:
                geolocator = Nominatim(user_agent="sobap_manager_final_v2")
                # 💡 [핵심] exactly_one=False 로 설정하여 모든 검색 결과를 가져옵니다.
                results = geolocator.geocode(search_addr, exactly_one=False, timeout=10)
                
                if results:
                    st.session_state.search_results = results
                    st.success(f"{len(results)}개의 비슷한 주소를 찾았습니다.")
                else:
                    st.session_state.search_results = []
                    st.warning("정확한 주소를 찾을 수 없습니다.")
            except:
                st.error("주소 서비스 연결 지연 중입니다. 다시 시도해 주세요.")

        # 검색 결과가 있을 경우 선택 창 표시
        if st.session_state.search_results:
            options = {res.address: (res.latitude, res.longitude) for res in st.session_state.search_results}
            selected_address = st.selectbox("진짜 주소를 선택하세요", list(options.keys()))
            
            if st.button("📍 선택한 위치 확인"):
                lat, lon = options[selected_address]
                st.session_state.temp_loc = {"lat": lat, "lon": lon, "addr": selected_address}
                st.session_state.map_center = [lat, lon]
                st.session_state.map_zoom = 16
                st.rerun()

        # 3️⃣ 영업권 검토 및 선점
        if st.session_state.temp_loc:
            st.markdown("---")
            st.header("3️⃣ 최종 검토 및 선점")
            t = st.session_state.temp_loc
            
            is_blocked = False
            for _, row in df.iterrows():
                if row['owner'] != selected_owner:
                    dist = geodesic((t['lat'], t['lon']), (row['lat'], row['lon'])).meters
                    if dist < 500:
                        st.error(f"⚠️ 선점 불가: {row['owner']} 점주와 {int(dist)}m 거리!")
                        is_blocked = True
                        break
            
            if not is_blocked:
                st.info(f"✅ {selected_owner} 님을 위한 추천 구역")
                if st.button(f"🚩 선택한 주소 선점!", use_container_width=True):
                    payload = {"action": "add", "lat": t['lat'], "lon": t['lon'], "owner": selected_owner}
                    requests.post(API_URL, data=json.dumps(payload))
                    st.session_state.temp_loc = None
                    st.session_state.search_results = []
                    st.success("선점 완료!")
                    st.rerun()

# =========================================================
# 🗺️ 오른쪽 메인 화면: 실시간 지도
# =========================================================
st.title("🗺️ 소중한밥상 실시간 영업권 지도")

m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

for _, row in df.iterrows():
    try:
        is_mine = (row['owner'] == selected_owner)
        color = "red" if is_mine else "blue"
        folium.Marker([row['lat'], row['lon']], popup=f"점주: {row['owner']}", icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=500, color=color, fill=True, fill_opacity=0.15).add_to(m)
    except: continue

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=500, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}_{st.session_state.map_zoom}")
