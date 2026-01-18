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

# =========================================================
# 🍱 왼쪽 사이드바: 단계별 통합 관리 (장소 이름 중심)
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # 1️⃣ 점주 선택
    st.header("1️⃣ 점주 선택")
    # 중복 제거된 점주 리스트 추출 (구분자 '|' 앞부분만 사용)
    all_names = df['owner'].astype(str).tolist()
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in all_names])))
    
    selected_owner = st.selectbox("관리할 점주 선택", ["점주 선택"] + unique_owners)
    
    st.markdown("---")

    if selected_owner != "점주 선택":
        # 📂 [개선] 현재 선점 목록 확인/삭제 (장소 이름 표시)
        with st.expander("📍 현재 선점 목록 확인/삭제", expanded=True):
            # 해당 점주가 포함된 모든 행 필터링
            owner_data = df[df['owner'].str.contains(selected_owner, na=False)]
            
            if not owner_data.empty:
                for idx, row in owner_data.iterrows():
                    # 저장된 이름에서 장소 정보만 추출 (예: "김상희 점주 | 암남동 현대" -> "암남동 현대")
                    display_name = row['owner'].split('|')[-1].strip() if '|' in str(row['owner']) else "상세 주소 없음"
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"🏠 **{display_name}**")
                    with col2:
                        if st.button("삭제", key=f"del_{idx}"):
                            new_df = df.drop(idx)
                            payload = {"action": "sync", "data": [new_df.columns.tolist()] + new_df.values.tolist()}
                            requests.post(API_URL, data=json.dumps(payload))
                            st.rerun()
            else:
                st.write("선점 내역이 없습니다.")

        # 2️⃣ 주소 및 동네 검색
        st.header("2️⃣ 주소 및 동네 검색")
        search_addr = st.text_input("검색어 입력", placeholder="예: 암남동 현대, 중동 롯데캐슬")
        
        if st.button("🔍 위치 후보 검색"):
            try:
                geolocator = Nominatim(user_agent="sobap_pro_v4")
                results = geolocator.geocode(search_addr, exactly_one=False, timeout=10, geometry='geojson')
                if results:
                    st.session_state.search_results = results
                    st.success(f"{len(results)}개의 결과 발견")
                else:
                    st.warning("결과가 없습니다.")
            except:
                st.error("연결 지연 중입니다.")

        if st.session_state.search_results:
            res_options = {res.address: res for res in st.session_state.search_results}
            selected_res_addr = st.selectbox("선점할 주소를 선택하세요", list(res_options.keys()))
            
            if st.button("📍 지도에서 위치 확인"):
                target = res_options[selected_res_addr]
                is_area = target.raw.get('type') in ['administrative', 'suburb', 'city_district']
                st.session_state.temp_loc = {
                    "lat": target.latitude, "lon": target.longitude, 
                    "addr": selected_res_addr, "is_area": is_area,
                    "geojson": target.raw.get('geojson') if is_area else None
                }
                st.session_state.map_center = [target.latitude, target.longitude]
                st.session_state.map_zoom = 14 if is_area else 17
                st.rerun()

        # 3️⃣ 최종 선점 (점주 이름 | 장소 이름 형식으로 저장)
        if st.session_state.temp_loc:
            st.markdown("---")
            st.header("3️⃣ 구역 확인 및 선점")
            t = st.session_state.temp_loc
            
            # 주소에서 핵심 단어만 추출 (너무 길면 앞부분만)
            short_addr = t['addr'].split(',')[0]
            # 💡 [핵심] 저장 형식을 '점주명 | 장소명'으로 통일
            full_save_name = f"{selected_owner} | {short_addr}"
            
            # 100M 거리 제한 체크
            is_blocked = False
            if not t['is_area']:
                for _, row in df.iterrows():
                    # 자기 자신의 다른 지점은 제외하고 타 점주와만 비교
                    if selected_owner not in str(row['owner']):
                        dist = geodesic((t['lat'], t['lon']), (row['lat'], row['lon'])).meters
                        if dist < 100:
                            st.error(f"⚠️ 선점 불가: 타 점주 구역과 {int(dist)}m 거리!")
                            is_blocked = True
                            break
            
            if not is_blocked:
                if st.button(f"🚩 '{short_addr}' 선점하기!", use_container_width=True):
                    payload = {"action": "add", "lat": t['lat'], "lon": t['lon'], "owner": full_save_name}
                    requests.post(API_URL, data=json.dumps(payload))
                    st.session_state.temp_loc = None
                    st.success("성공적으로 선점되었습니다!")
                    st.rerun()

# =========================================================
# 🗺️ 오른쪽 메인 화면: 실시간 지도
# =========================================================
st.title("🗺️ 소중한밥상 영업권 관제 센터")

m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

for _, row in df.iterrows():
    try:
        # 현재 선택된 점주가 포함되어 있는지 확인
        row_owner_name = str(row['owner']).split('|')[0].strip()
        is_mine = (row_owner_name == selected_owner)
        color = "red" if is_mine else "blue"
        
        folium.Marker(
            [row['lat'], row['lon']], 
            popup=f"정보: {row['owner']}", 
            icon=folium.Icon(color=color)
        ).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=100, color=color, fill=True, fill_opacity=0.15).add_to(m)
    except: continue

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    if t['is_area'] and t['geojson']:
        folium.GeoJson(t['geojson'], style_function=lambda x: {'fillColor': '#2ecc71', 'color': '#27ae60', 'weight': 2, 'fillOpacity': 0.3}).add_to(m)
    else:
        folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
        folium.Circle(location=[t['lat'], t['lon']], radius=100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
