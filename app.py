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
# 🍱 왼쪽 사이드바: 장소 중심의 간결한 관리
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # 1️⃣ 점주 선택
    st.header("1️⃣ 점주 선택")
    # 이름 정제 (점주 이름만 추출)
    all_names = df['owner'].astype(str).tolist()
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in all_names])))
    
    selected_owner = st.selectbox("관리할 점주를 선택하세요", ["선택"] + unique_owners)
    
    st.markdown("---")

    if selected_owner != "선택":
        # 📂 [개선] 현재 선점 목록 (장소 이름만 표시)
        st.header("📍 현재 선점 목록")
        # 해당 점주 데이터 필터링
        owner_data = df[df['owner'].str.contains(selected_owner, na=False)]
        
        if not owner_data.empty:
            for idx, row in owner_data.iterrows():
                full_val = str(row['owner'])
                # 💡 [핵심] '|' 기호 뒤의 '장소 이름'만 가져옵니다.
                if '|' in full_val:
                    place_name = full_val.split('|')[-1].strip()
                else:
                    place_name = full_val # 옛날 데이터는 그대로 표시
                
                col1, col2 = st.columns([4, 1])
                with col1:
                    # 클릭 시 해당 위치로 지도 이동
                    if st.button(f"🏠 {place_name}", key=f"move_{idx}"):
                        st.session_state.map_center = [row['lat'], row['lon']]
                        st.session_state.map_zoom = 17
                        st.rerun()
                with col2:
                    if st.button("삭제", key=f"del_{idx}"):
                        new_df = df.drop(idx)
                        payload = {"action": "sync", "data": [new_df.columns.tolist()] + new_df.values.tolist()}
                        requests.post(API_URL, data=json.dumps(payload))
                        st.rerun()
        else:
            st.write("선점한 내역이 없습니다.")

        st.markdown("---")

        # 2️⃣ 새 장소 검색
        st.header("2️⃣ 새 장소 검색 및 추가")
        search_addr = st.text_input("아파트명 또는 동네 입력", placeholder="예: 암남동 현대")
        
        if st.button("🔍 검색"):
            try:
                geolocator = Nominatim(user_agent="sobap_final_v6")
                results = geolocator.geocode(search_addr, exactly_one=False, timeout=10)
                if results:
                    st.session_state.search_results = results
                    st.success(f"{len(results)}개의 결과 발견")
                else:
                    st.warning("결과를 찾을 수 없습니다.")
            except:
                st.error("연결 지연 중... 다시 시도하세요.")

        if st.session_state.search_results:
            res_map = {res.address: res for res in st.session_state.search_results}
            selected_res = st.selectbox("정확한 주소를 고르세요", list(res_map.keys()))
            
            if st.button("📍 지도에서 위치 확인"):
                t = res_map[selected_res]
                # 장소 이름만 짧게 추출 (첫 번째 단어)
                short_name = selected_res.split(',')[0].strip()
                st.session_state.temp_loc = {"lat": t.latitude, "lon": t.longitude, "name": short_name}
                st.session_state.map_center = [t.latitude, t.longitude]
                st.session_state.map_zoom = 17
                st.rerun()

        # 3️⃣ 최종 선점 (100M 체크)
        if st.session_state.temp_loc:
            st.markdown("---")
            t = st.session_state.temp_loc
            
            is_blocked = False
            for _, row in df.iterrows():
                if selected_owner not in str(row['owner']):
                    if geodesic((t['lat'], t['lon']), (row['lat'], row['lon'])).meters < 100:
                        st.error("⚠️ 타 점주와 100m 이내입니다!")
                        is_blocked = True
                        break
            
            if not is_blocked:
                if st.button(f"🚩 '{t['name']}' 선점!", use_container_width=True):
                    # 💡 [핵심] '점주명 | 장소명' 형식으로 저장
                    save_val = f"{selected_owner} | {t['name']}"
                    payload = {"action": "add", "lat": t['lat'], "lon": t['lon'], "owner": save_val}
                    requests.post(API_URL, data=json.dumps(payload))
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
        # 점주 이름만 따와서 색상 결정
        owner_only = str(row['owner']).split('|')[0].strip()
        is_mine = (owner_only == selected_owner)
        color = "red" if is_mine else "blue"
        
        folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=100, color=color, fill=True, fill_opacity=0.15).add_to(m)
    except: continue

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
