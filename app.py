import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 영업권 관리", layout="wide")

# 2. 구글 앱 스크립트 URL
API_URL = "https://script.google.com/macros/s/AKfycbxmLywtQIA-6Ay5_KczYt3zNIoGekzkdWD4I3X80PORIMw8gUNHMsZTvip8LXdopxTJ/exec"

def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            # ⚠️ 추가된 안전 장치: 숫자가 아닌 데이터나 빈 칸은 제거합니다.
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
            df = df.dropna(subset=['lat', 'lon'])
            return df
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])
    except:
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])

df = get_data()

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [37.5665, 126.9780]
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = 11
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'last_selected' not in st.session_state: st.session_state.last_selected = None

# =========================================================
# 🍱 왼쪽 사이드바: 관리 프로세스
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    st.header("1️⃣ 점주 선택")
    unique_owners = df['owner'].unique().tolist()
    selected_owner = st.selectbox("관리할 점주 선택", ["점주 선택"] + unique_owners)
    
    # 점주 선택 시 지도 자동 이동
    if selected_owner != "점주 선택" and selected_owner != st.session_state.last_selected:
        owner_df = df[df['owner'] == selected_owner]
        if not owner_df.empty:
            st.session_state.map_center = [owner_df['lat'].mean(), owner_df['lon'].mean()]
            st.session_state.map_zoom = 14
            st.session_state.last_selected = selected_owner
            st.rerun()

    st.markdown("---")

    if selected_owner != "점주 선택":
        st.header("2️⃣ 주소 검색 및 확인")
        search_addr = st.text_input("검색할 주소 입력")
        
        if st.button("🔍 주소 위치 확인"):
            geolocator = Nominatim(user_agent="sobap_bot_final")
            location = geolocator.geocode(search_addr)
            if location:
                st.session_state.temp_loc = {"lat": location.latitude, "lon": location.longitude, "addr": search_addr}
                st.session_state.map_center = [location.latitude, location.longitude]
                st.session_state.map_zoom = 16
                st.rerun()
            else:
                st.error("주소를 찾을 수 없습니다.")

        if st.session_state.temp_loc:
            st.markdown("---")
            st.header("3️⃣ 영업권 검토 및 선점")
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
                st.info("✅ 주변 500m 이내 타 점주 없음")
                if st.button(f"🚩 '{selected_owner}' 이름으로 선점!", use_container_width=True):
                    payload = {"action": "add", "lat": t['lat'], "lon": t['lon'], "owner": selected_owner}
                    requests.post(API_URL, data=json.dumps(payload))
                    st.session_state.temp_loc = None
                    st.success("선점 완료!")
                    st.rerun()

# =========================================================
# 🗺️ 오른쪽 메인 화면: 지능형 지도
# =========================================================
st.title("🗺️ 소중한밥상 실시간 영업권 지도")

# 지도 생성
m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

# ⚠️ 에러 방지를 위해 위도/경도가 올바른 데이터만 마커를 찍습니다.
for _, row in df.iterrows():
    try:
        is_mine = (row['owner'] == selected_owner)
        color = "red" if is_mine else "blue"
        
        folium.Marker(
            [float(row['lat']), float(row['lon'])], 
            popup=f"점주: {row['owner']}", 
            icon=folium.Icon(color=color)
        ).add_to(m)
        
        folium.Circle(
            location=[float(row['lat']), float(row['lon'])], 
            radius=500, 
            color=color, 
            fill=True, 
            fill_opacity=0.15
        ).add_to(m)
    except:
        continue # 데이터에 문제가 있는 행은 그냥 건너뜁니다.

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=500, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
