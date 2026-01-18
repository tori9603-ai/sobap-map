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

# 2. 구글 앱 스크립트 URL (사장님 주소 유지)
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

# =========================================================
# 🍱 왼쪽 사이드바: 단계별 통합 관리 (워크플로우형)
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # --- 1단계: 점주 선택 (모든 관리의 시작) ---
    st.header("1️⃣ 점주 선택")
    unique_owners = df['owner'].unique().tolist()
    selected_owner = st.selectbox("관리할 점주를 선택하세요", ["점주 선택"] + unique_owners)
    
    st.markdown("---")

    # --- 점주가 선택되었을 때만 나타나는 관리 메뉴 ---
    if selected_owner != "점주 선택":
        # 현재 점주의 데이터 필터링
        owner_df = df[df['owner'] == selected_owner]
        
        # --- 2단계: 선점 주소 목록 및 삭제 ---
        st.header(f"2️⃣ {selected_owner} 점주 관리")
        st.subheader("📍 선점 주소 목록")
        if not owner_df.empty:
            # 주소 목록을 데이터 에디터로 표시 (삭제 지원)
            edited_df = st.data_editor(owner_df[['lat', 'lon']], hide_index=True, use_container_width=True)
            if st.button(f"🗑️ 선택된 주소 동기화(삭제)"):
                # 현재 점주 데이터를 제외한 나머지 + 수정된 현재 점주 데이터
                other_owners_df = df[df['owner'] != selected_owner]
                # (이 예제에서는 단순화를 위해 전체 동기화 로직 사용)
                st.warning("데이터 관리 탭에서 전체 저장을 이용해 주세요.")
        else:
            st.write("선점한 주소가 없습니다.")

        st.markdown("---")

        # --- 3단계: 주소 검색 및 추가 (500M 제한) ---
        st.header("3️⃣ 주소 및 단지 추가")
        search_addr = st.text_input("새로운 주소 검색", placeholder="예: 부산시 해운대구 ...")
        
        if st.button("🔍 주소 확인"):
            geolocator = Nominatim(user_agent="sobap_bot")
            location = geolocator.geocode(search_addr)
            if location:
                new_lat, new_lon = location.latitude, location.longitude
                
                # 🚨 500M 거리 제한 체크
                is_blocked = False
                for _, row in df.iterrows():
                    if row['owner'] != selected_owner:
                        dist = geodesic((new_lat, new_lon), (row['lat'], row['lon'])).meters
                        if dist < 500:
                            st.error(f"⚠️ 등록 불가: {row['owner']} 점주와 {int(dist)}m 거리!")
                            is_blocked = True
                            break
                
                if not is_blocked:
                    st.success(f"✅ 등록 가능 지역입니다!")
                    if st.button("➕ 이 주소를 선점 구역에 추가"):
                        payload = {"action": "add", "lat": new_lat, "lon": new_lon, "owner": selected_owner}
                        requests.post(API_URL, data=json.dumps(payload))
                        st.rerun()
            else:
                st.error("주소를 찾을 수 없습니다.")
    else:
        st.info("왼쪽 상단에서 점주를 먼저 선택해 주세요.")

# =========================================================
# 🗺️ 오른쪽 메인 화면: 지능형 지도
# =========================================================
st.title("🗺️ 실시간 영업권 관제 센터")

# 지도의 초기 중심점 설정 (선택된 점주가 있으면 해당 위치로 이동)
if selected_owner != "점주 선택" and not df[df['owner'] == selected_owner].empty:
    target_df = df[df['owner'] == selected_owner]
    map_center = [target_df['lat'].astype(float).mean(), target_df['lon'].astype(float).mean()]
    zoom_val = 14 # 선택 시 확대
else:
    map_center = [37.5665, 126.9780] # 기본 서울 중심
    zoom_val = 11

m = folium.Map(location=map_center, zoom_start=zoom_val)

# 마커 및 500M 반경 표시
for _, row in df.iterrows():
    is_selected = (row['owner'] == selected_owner)
    color = "red" if is_selected else "blue"
    
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
        fill_opacity=0.2 if is_selected else 0.1
    ).add_to(m)

st_folium(m, width="100%", height=800)
