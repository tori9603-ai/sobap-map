import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 관리자", layout="wide")

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

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [37.5665, 126.9780]
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = 11
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []

# =========================================================
# 🍱 사이드바: 직관적인 점주 및 장소 관리
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # 1️⃣ 점주 선택
    st.header("1️⃣ 점주 선택")
    all_owners = sorted(list(set([str(name).split('|')[0].strip() for name in df['owner']])))
    selected_owner = st.selectbox("점주를 선택하세요", ["선택"] + all_owners)
    
    st.markdown("---")

    if selected_owner != "선택":
        # 📂 선점 목록 (장소명만 간단히 표시)
        st.header("📍 현재 선점 목록")
        # 해당 점주의 데이터만 추출
        owner_df = df[df['owner'].str.contains(selected_owner, na=False)]
        
        if not owner_df.empty:
            for idx, row in owner_df.iterrows():
                # '|' 뒤의 주소만 가져오기 (없으면 전체 표시)
                place_display = str(row['owner']).split('|')[-1].strip() if '|' in str(row['owner']) else str(row['owner'])
                
                col1, col2 = st.columns([4, 1])
                with col1:
                    # 클릭하면 지도가 해당 위치로 이동
                    if st.button(f"🏠 {place_display}", key=f"btn_{idx}"):
                        st.session_state.map_center = [row['lat'], row['lon']]
                        st.session_state.map_zoom = 17
                        st.rerun()
                with col2:
                    if st.button("삭제", key=f"del_{idx}"):
                        new_df = df.drop(idx)
                        requests.post(API_URL, data=json.dumps({"action": "sync", "data": [new_df.columns.tolist()] + new_df.values.tolist()}))
                        st.rerun()
        else:
            st.write("선점한 곳이 없습니다.")

        st.markdown("---")

        # 2️⃣ 주소 검색 및 추가
        st.header("2️⃣ 새 장소 검색")
        search_addr = st.text_input("아파트명/동네 입력")
        
        if st.button("🔍 검색"):
            try:
                geolocator = Nominatim(user_agent="sobap_simple_v1")
                results = geolocator.geocode(search_addr, exactly_one=False, timeout=10)
                if results:
                    st.session_state.search_results = results
                else:
                    st.warning("결과가 없습니다.")
            except:
                st.error("연결 지연 중...")

        if st.session_state.search_results:
            res_map = {res.address: res for res in st.session_state.search_results}
            selected_res = st.selectbox("정확한 주소 선택", list(res_map.keys()))
            
            if st.button("📍 위치 확인"):
                t = res_map[selected_res]
                st.session_state.temp_loc = {"lat": t.latitude, "lon": t.longitude, "name": selected_res.split(',')[0].strip()}
                st.session_state.map_center = [t.latitude, t.longitude]
                st.session_state.map_zoom = 17
                st.rerun()

        # 3️⃣ 100M 체크 후 선점
        if st.session_state.temp_loc:
            t = st.session_state.temp_loc
            is_blocked = False
            for _, row in df.iterrows():
                if selected_owner not in str(row['owner']):
                    if geodesic((t['lat'], t['lon']), (row['lat'], row['lon'])).meters < 100:
                        st.error("⚠️ 100m 이내 타 점주 구역!")
                        is_blocked = True
                        break
            
            if not is_blocked:
                if st.button(f"🚩 '{t['name']}' 선점!", use_container_width=True):
                    # 저장할 때 '점주 | 장소명' 형식으로 저장 (불러올 때 편함)
                    save_name = f"{selected_owner} | {t['name']}"
                    requests.post(API_URL, data=json.dumps({"action": "add", "lat": t['lat'], "lon": t['lon'], "owner": save_name}))
                    st.session_state.temp_loc = None
                    st.success("등록 완료!")
                    st.rerun()

# =========================================================
# 🗺️ 메인 화면: 지도 고정
# =========================================================
st.title("🗺️ 소중한밥상 관제 센터")

m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

for _, row in df.iterrows():
    try:
        is_mine = (selected_owner in str(row['owner']))
        color = "red" if is_mine else "blue"
        folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=100, color=color, fill=True, fill_opacity=0.2).add_to(m)
    except: continue

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
