import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

st.set_page_config(page_title="소중한밥상 영업권 관리 시스템", layout="wide")

# 1. 구글 앱 스크립트 URL (기존 주소 유지)
API_URL = "https://script.google.com/macros/s/AKfycbxmLywtQIA-6Ay5_KczYt3zNIoGekzkdWD4I3X80PORIMw8gUNHMsZTvip8LXdopxTJ/exec"

# --- 데이터 로드 ---
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
# 🍱 사이드바: 1. 점주 관리 / 2. 주소 및 단지
# =========================================================
st.sidebar.title("🍱 관리 시스템")
main_menu = st.sidebar.radio("카테고리 선택", ["1. 점주 관리", "2. 주소 및 단지"])

# 세션 상태로 선택된 점주 기억
if 'selected_owner' not in st.session_state:
    st.session_state.selected_owner = None

# --- [카테고리 1] 점주 관리 ---
if main_menu == "1. 점주 관리":
    st.sidebar.subheader("👤 점주 목록")
    unique_owners = df['owner'].unique().tolist()
    
    # 점주 선택
    selected = st.sidebar.selectbox("점주를 선택하세요", ["선택 안 함"] + unique_owners)
    if selected != "선택 안 함":
        st.session_state.selected_owner = selected
        
        # 해당 점주 삭제 기능
        if st.sidebar.button(f"❌ {selected} 점주 전체 삭제"):
            new_df = df[df['owner'] != selected]
            full_data = [new_df.columns.tolist()] + new_df.values.tolist()
            requests.post(API_URL, data=json.dumps({"action": "sync", "data": full_data}))
            st.sidebar.success("삭제 완료!")
            st.rerun()
    else:
        st.session_state.selected_owner = None

# --- [카테고리 2] 주소 및 단지 ---
elif main_menu == "2. 주소 및 단지":
    st.sidebar.subheader("🔍 주소 검색 및 추가")
    
    if st.session_state.selected_owner is None:
        st.sidebar.warning("먼저 '1. 점주 관리'에서 점주를 선택해주세요.")
    else:
        st.sidebar.info(f"선택된 점주: **{st.session_state.selected_owner}**")
        search_addr = st.sidebar.text_input("추가할 주소를 검색하세요")
        
        if st.sidebar.button("주소 검색"):
            geolocator = Nominatim(user_agent="sobap_bot")
            location = geolocator.geocode(search_addr)
            
            if location:
                new_lat, new_lon = location.latitude, location.longitude
                st.session_state.temp_loc = {"lat": new_lat, "lon": new_lon, "addr": search_addr}
                st.sidebar.success(f"검색 결과: {search_addr}")
            else:
                st.sidebar.error("주소를 찾을 수 없습니다.")

        # 검색된 좌표가 있을 때만 추가/삭제 버튼 표시
        if 'temp_loc' in st.session_state:
            t = st.session_state.temp_loc
            
            # 🚨 500M 거리 제한 로직
            is_blocked = False
            for _, row in df.iterrows():
                # 다른 점주와의 거리만 계산
                if row['owner'] != st.session_state.selected_owner:
                    dist = geodesic((t['lat'], t['lon']), (row['lat'], row['lon'])).meters
                    if dist < 500:
                        st.sidebar.error(f"⚠️ 경고: {row['owner']} 점주와 {int(dist)}m 거리에 있어 등록 불가!")
                        is_blocked = True
                        break
            
            if not is_blocked:
                if st.sidebar.button(f"➕ {st.session_state.selected_owner} 칸에 주소 추가"):
                    payload = {"action": "add", "lat": t['lat'], "lon": t['lon'], "owner": st.session_state.selected_owner}
                    requests.post(API_URL, data=json.dumps(payload))
                    st.sidebar.success("주소 등록 완료!")
                    st.rerun()

# =========================================================
# 🗺️ 메인 화면: 실시간 지도 및 영업권 표시
# =========================================================
st.title("🗺️ 소중한밥상 영업권 지도")

# 지도 생성
m = folium.Map(location=[37.5665, 126.9780], zoom_start=12)

# 모든 지점 표시 및 500M 원 그리기
for _, row in df.iterrows():
    # 선택된 점주와 나머지 점주 색상 구분
    color = "red" if row['owner'] == st.session_state.selected_owner else "gray"
    fill_color = "red" if row['owner'] == st.session_state.selected_owner else "gray"
    
    # 1. 지점 마커
    folium.Marker(
        [row['lat'], row['lon']], 
        popup=f"점주: {row['owner']}",
        icon=folium.Icon(color=color)
    ).add_to(m)
    
    # 2. 500M 영업권 영역 표시
    folium.Circle(
        location=[row['lat'], row['lon']],
        radius=500, # 500미터
        color=color,
        fill=True,
        fill_color=fill_color,
        fill_opacity=0.2
    ).add_to(m)

# 검색 중인 임시 위치 표시
if 'temp_loc' in st.session_state:
    folium.Marker(
        [st.session_state.temp_loc['lat'], st.session_state.temp_loc['lon']],
        icon=folium.Icon(color="green", icon="info-sign"),
        tooltip="검색된 위치"
    ).add_to(m)

st_folium(m, width="100%", height=750)
