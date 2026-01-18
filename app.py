import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 관리 시스템", layout="wide")

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
# 🍱 왼쪽 사이드바: 장소명만 직관적으로 표시
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    st.header("1️⃣ 점주 선택")
    # 점주 이름만 깨끗하게 추출
    raw_owners = df['owner'].astype(str).tolist()
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in raw_owners])))
    selected_owner = st.selectbox("점주를 선택하세요", ["선택"] + unique_owners)
    
    st.markdown("---")

    if selected_owner != "선택":
        st.header("📍 현재 선점 목록")
        # 선택된 점주의 데이터만 필터링
        owner_data = df[df['owner'].str.contains(selected_owner, na=False)]
        
        if not owner_data.empty:
            for idx, row in owner_data.iterrows():
                full_val = str(row['owner'])
                
                # 💡 [핵심] 점주 이름을 무조건 제거하고 뒤의 장소명만 추출
                if '|' in full_val:
                    # '점주명 | 장소명' 구조에서 뒷부분만 가져옴
                    display_name = full_val.split('|')[-1].strip()
                else:
                    # 예전 데이터(점주명만 있는 경우)는 표시하지 않거나 별도 처리
                    display_name = "장소 정보 없음" if full_val.strip() == selected_owner else full_val
                
                col1, col2 = st.columns([4, 1])
                with col1:
                    # 버튼 클릭 시 해당 장소로 지도 이동
                    if st.button(f"🏠 {display_name}", key=f"btn_{idx}"):
                        st.session_state.map_center = [row['lat'], row['lon']]
                        st.session_state.map_zoom = 17
                        st.rerun()
                with col2:
                    if st.button("삭제", key=f"del_{idx}"):
                        new_df = df.drop(idx)
                        requests.post(API_URL, data=json.dumps({"action": "sync", "data": [new_df.columns.tolist()] + new_df.values.tolist()}))
                        st.rerun()
        else:
            st.write("선점 내역이 없습니다.")

        st.markdown("---")

        # 2️⃣ 장소 검색 및 추가
        st.header("2️⃣ 새 장소 검색")
        search_addr = st.text_input("아파트명 또는 동네 입력")
        
        if st.button("🔍 위치 찾기"):
            try:
                geolocator = Nominatim(user_agent="sobap_final_fix")
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
            
            if st.button("📍 지도에서 확인"):
                t = res_map[selected_res]
                # 주소에서 아파트/동네 이름만 추출
                short_name = selected_res.split(',')[0].strip()
                st.session_state.temp_loc = {"lat": t.latitude, "lon": t.longitude, "name": short_name}
                st.session_state.map_center = [t.latitude, t.longitude]
                st.session_state.map_zoom = 17
                st.rerun()

        if st.session_state.temp_loc:
            t = st.session_state.temp_loc
            if st.button(f"🚩 '{t['name']}' 선점!", use_container_width=True):
                # 💡 [핵심] '점주명 | 장소명'으로 명확히 구분하여 저장
                save_val = f"{selected_owner} | {t['name']}"
                requests.post(API_URL, data=json.dumps({"action": "add", "lat": t['lat'], "lon": t['lon'], "owner": save_val}))
                st.session_state.temp_loc = None
                st.success("등록 완료!")
                st.rerun()

# =========================================================
# 🗺️ 오른쪽 메인 화면: 지도 고정
# =========================================================
st.title("🗺️ 소중한밥상 실시간 관제 센터")

m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

for _, row in df.iterrows():
    try:
        owner_raw = str(row['owner']).split('|')[0].strip()
        is_mine = (owner_raw == selected_owner)
        color = "red" if is_mine else "blue"
        folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=100, color=color, fill=True, fill_opacity=0.15).add_to(m)
    except: continue

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
