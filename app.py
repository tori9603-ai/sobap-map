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
            return pd.DataFrame(data[1:], columns=data[0])
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])
    except:
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])

df = get_data()

# 세션 상태 초기화 (검색된 위치 및 지도 중심점 기억)
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'map_center' not in st.session_state: st.session_state.map_center = [37.5665, 126.9780]
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = 11

# =========================================================
# 🍱 왼쪽 사이드바: 단계별 통합 관리
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # --- 1단계: 점주 선택 ---
    st.header("1️⃣ 점주 선택")
    unique_owners = df['owner'].unique().tolist()
    selected_owner = st.selectbox("관리할 점주 선택", ["점주 선택"] + unique_owners)
    
    st.markdown("---")

    # --- 2단계: 주소 검색 및 시각적 확인 ---
    if selected_owner != "점주 선택":
        st.header("2️⃣ 주소 검색 및 확인")
        search_addr = st.text_input("검색할 주소 입력", placeholder="예: 부산시 해운대구 ...")
        
        if st.button("🔍 주소 위치 확인"):
            geolocator = Nominatim(user_agent="sobap_bot")
            location = geolocator.geocode(search_addr)
            if location:
                # 검색된 위치 저장 및 지도 중심 이동
                st.session_state.temp_loc = {
                    "lat": location.latitude, 
                    "lon": location.longitude, 
                    "addr": search_addr
                }
                st.session_state.map_center = [location.latitude, location.longitude]
                st.session_state.map_zoom = 16 # 주소 확인을 위해 크게 확대
                st.success("지도에서 초록색 핀 위치를 확인하세요!")
            else:
                st.error("주소를 찾을 수 없습니다.")

        # --- 3단계: 거리 제한 체크 및 선점 ---
        if st.session_state.temp_loc:
            st.markdown("---")
            st.header("3️⃣ 영업권 검토 및 선점")
            t = st.session_state.temp_loc
            
            # 🚨 500M 거리 제한 체크
            is_blocked = False
            for _, row in df.iterrows():
                if row['owner'] != selected_owner:
                    dist = geodesic((t['lat'], t['lon']), (row['lat'], row['lon'])).meters
                    if dist < 500:
                        st.error(f"⚠️ 선점 불가: {row['owner']} 점주와 {int(dist)}m 거리!")
                        is_blocked = True
                        break
            
            if not is_blocked:
                st.info(f"✅ 주변 500m 이내 타 점주 없음")
                if st.button(f"🚩 '{selected_owner}' 이름으로 선점!", use_container_width=True):
                    payload = {"action": "add", "lat": t['lat'], "lon": t['lon'], "owner": selected_owner}
                    requests.post(API_URL, data=json.dumps(payload))
                    st.session_state.temp_loc = None # 선점 후 임시 핀 제거
                    st.success("성공적으로 선점되었습니다!")
                    st.rerun()
    else:
        st.info("먼저 점주를 선택해 주세요.")

# =========================================================
# 🗺️ 오른쪽 메인 화면: 실시간 지도
# =========================================================
st.title("🗺️ 실시간 영업권 관제 센터")

# 지도 생성 (세션에 저장된 중심점과 줌 사용)
m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

# 1. 기존 데이터 표시
for _, row in df.iterrows():
    is_mine = (row['owner'] == selected_owner)
    color = "red" if is_mine else "blue"
    
    folium.Marker(
        [row['lat'], row['lon']], 
        popup=f"점주: {row['owner']}",
        icon=folium.Icon(color=color)
    ).add_to(m)
    
    folium.Circle(
        location=[row['lat'], row['lon']],
        radius=500,
        color=color,
        fill=True,
        fill_opacity=0.2 if is_mine else 0.1
    ).add_to(m)

# 2. 검색 중인 임시 위치 (초록색 핀) 표시
if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker(
        [t['lat'], t['lon']],
        icon=folium.Icon(color="green", icon="star"),
        tooltip="여기가 맞나요?",
        popup="검색된 위치 (확인 후 왼쪽 선점 버튼 클릭)"
    ).add_to(m)
    # 확인용 500m 가이드 라인
    folium.Circle(
        location=[t['lat'], t['lon']],
        radius=500,
        color="green",
        dash_array='5, 5',
        fill=False
    ).add_to(m)

st_folium(m, width="100%", height=800)
