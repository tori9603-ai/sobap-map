import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 통합 관제 센터", layout="wide")

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
# 🍱 왼쪽 사이드바: 단계별 통합 관리
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
        # 📂 선점 주소 목록 관리
        with st.expander("📍 현재 선점 목록 확인/삭제"):
            owner_data = df[df['owner'] == selected_owner]
            if not owner_data.empty:
                for idx, row in owner_data.iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1: st.write(f"🏠 {row['owner']} 구역")
                    with col2:
                        if st.button("삭제", key=f"del_{idx}"):
                            new_df = df.drop(idx)
                            payload = {"action": "sync", "data": [new_df.columns.tolist()] + new_df.values.tolist()}
                            requests.post(API_URL, data=json.dumps(payload))
                            st.rerun()
            else:
                st.write("선점 내역 없음")

        # 2️⃣ 주소/동네 검색
        st.header("2️⃣ 주소 및 동네 검색")
        search_addr = st.text_input("검색어 입력 (예: 암남동, 해운대 롯데캐슬)")
        
        if st.button("🔍 위치 후보 검색"):
            try:
                geolocator = Nominatim(user_agent="sobap_area_manager_v1")
                # 💡 [핵심] geometry 정보를 가져오도록 설정
                results = geolocator.geocode(search_addr, exactly_one=False, timeout=10, geometry='geojson')
                if results:
                    st.session_state.search_results = results
                    st.success(f"{len(results)}개의 검색 결과를 찾았습니다.")
                else:
                    st.warning("검색 결과가 없습니다.")
            except:
                st.error("서비스 연결 지연 중입니다.")

        if st.session_state.search_results:
            # 주소 목록 생성
            res_options = {res.address: res for res in st.session_state.search_results}
            selected_res_addr = st.selectbox("정확한 위치/동네를 선택하세요", list(res_options.keys()))
            
            if st.button("📍 지도에서 구역 확인"):
                target = res_options[selected_res_addr]
                # 동네(administrative)인지 아파트(point)인지 구분
                is_area = target.raw.get('type') in ['administrative', 'suburb', 'city_district']
                
                st.session_state.temp_loc = {
                    "lat": target.latitude, 
                    "lon": target.longitude, 
                    "addr": selected_res_addr,
                    "geojson": target.raw.get('geojson') if is_area else None,
                    "is_area": is_area
                }
                st.session_state.map_center = [target.latitude, target.longitude]
                st.session_state.map_zoom = 14 if is_area else 17
                st.rerun()

        # 3️⃣ 최종 선점
        if st.session_state.temp_loc:
            st.markdown("---")
            st.header("3️⃣ 구역 확인 및 선점")
            t = st.session_state.temp_loc
            
            # 동네 선점 시 이름에 표시
            save_name = f"{selected_owner} (동네: {search_addr})" if t['is_area'] else selected_owner
            
            # 거리 제한 체크 (점 단위일 때만 100M 체크)
            is_blocked = False
            if not t['is_area']:
                for _, row in df.iterrows():
                    if row['owner'] != selected_owner:
                        dist = geodesic((t['lat'], t['lon']), (row['lat'], row['lon'])).meters
                        if dist < 100:
                            st.error(f"⚠️ 선점 불가: 타 지점과 {int(dist)}m 거리!")
                            is_blocked = True
                            break
            
            if not is_blocked:
                status_msg = "동네 전체를 선점합니다!" if t['is_area'] else "반경 100m 영업권을 선점합니다!"
                st.info(f"✅ 확인 완료: {status_msg}")
                if st.button(f"🚩 '{selected_owner}' 구역으로 최종 선점!", use_container_width=True):
                    payload = {"action": "add", "lat": t['lat'], "lon": t['lon'], "owner": save_name}
                    requests.post(API_URL, data=json.dumps(payload))
                    st.session_state.temp_loc = None
                    st.success("선점 완료되었습니다!")
                    st.rerun()

# =========================================================
# 🗺️ 오른쪽 메인 화면: 실시간 영업권 관제
# =========================================================
st.title("🗺️ 소중한밥상 실시간 영업권 지도")

m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

# 1. 기존 데이터 표시
for _, row in df.iterrows():
    try:
        is_mine = (selected_owner in str(row['owner']))
        color = "red" if is_mine else "blue"
        folium.Marker([row['lat'], row['lon']], popup=f"점주: {row['owner']}", icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=100, color=color, fill=True, fill_opacity=0.15).add_to(m)
    except: continue

# 2. 검색 중인 임시 구역 확인 (동네 경계선 그리기)
if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    if t['is_area'] and t['geojson']:
        # 💡 [핵심] 동네 경계선을 초록색 면으로 표시
        folium.GeoJson(
            t['geojson'],
            name="선점 구역 후보",
            style_function=lambda x: {'fillColor': '#2ecc71', 'color': '#27ae60', 'weight': 2, 'fillOpacity': 0.3}
        ).add_to(m)
        st.info("지도에 표시된 초록색 면적 전체를 선점하게 됩니다.")
    else:
        # 일반 주소는 핀과 100m 원 표시
        folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
        folium.Circle(location=[t['lat'], t['lon']], radius=100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}_{st.session_state.map_zoom}")
