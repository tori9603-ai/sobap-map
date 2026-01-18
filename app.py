import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 영업권 통합 관제", layout="wide")

# ⚠️ 사장님의 구글 웹 앱 URL (A:owner, B:address, C:lat, D:lon 순서)
API_URL = "https://script.google.com/macros/s/AKfycbxDw8kU3K2LzcaM0zOStvwBdsZs98zyjNzQtgxJlRnZcjTCA70RUEQMLmg4lHTCb9uQ/exec"

def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df['owner'] = df['owner'].astype(str).str.strip()
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            df = df[~df['owner'].isin(['0', '', 'nan'])]
            return df
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
    except:
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

df = get_data()

# --- 세션 상태 관리 ---
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756] # 기본 위치: 부산
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = 11
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []

# =========================================================
# 🍱 왼쪽 사이드바: 단계별 영업권 관리
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # 1️⃣ 점주 선택 및 관리
    st.header("1️⃣ 점주 선택")
    raw_owners = df['owner'].astype(str).tolist()
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in raw_owners if name.strip()])))
    selected_owner = st.selectbox("관리할 점주를 선택하세요", ["선택"] + unique_owners)
    
    with st.expander("➕ 신규 점주 등록"):
        add_name = st.text_input("새 점주 성함")
        if st.button("시트에 영구 등록"):
            if add_name:
                requests.post(API_URL, data=json.dumps({"action": "add", "owner": add_name, "address": "신규등록", "lat": 0, "lon": 0}))
                st.success(f"'{add_name}' 등록 완료!")
                st.rerun()

    st.markdown("---")

    if selected_owner != "선택":
        # 📍 현재 선점 내역 리스트
        st.header("📍 현재 선점 내역")
        owner_data = df[(df['owner'].str.contains(selected_owner, na=False)) & (df['lat'] != 0)]
        if not owner_data.empty:
            for idx, row in owner_data.iterrows():
                place_display = str(row['owner']).split('|')[-1].strip()
                c1, c2 = st.columns([4, 1])
                with c1:
                    if st.button(f"🏠 {place_display}", key=f"mv_{idx}"):
                        st.session_state.map_center = [row['lat'], row['lon']]
                        st.session_state.map_zoom = 15 if "[동네]" in place_display else 17
                        st.rerun()
                with c2:
                    if st.button("❌", key=f"rm_{idx}"):
                        new_df = df.drop(idx)
                        requests.post(API_URL, data=json.dumps({"action": "sync", "data": [new_df.columns.tolist()] + new_df.values.tolist()}))
                        st.rerun()
        else: st.write("선점된 구역 없음")

        st.markdown("---")

        # 2️⃣ 주소 검색 및 지도 확인 (검색 전용 모드)
        st.header("2️⃣ 영업권 검색 및 확인")
        search_addr = st.text_input("아파트명, 상세 주소, 또는 동네 입력", placeholder="예: 암남동 현대, 해운대 롯데캐슬")
        
        if st.button("🔍 한국 주소 찾기"):
            try:
                # 💡 대한민국 주소로 한정하여 검색
                geolocator = Nominatim(user_agent=f"sobap_final_{int(time.time())}")
                res = geolocator.geocode(search_addr, exactly_one=False, timeout=15, country_codes='kr', geometry='geojson')
                if res:
                    st.session_state.search_results = res
                    st.success(f"{len(res)}개의 장소를 찾았습니다.")
                else:
                    st.warning("한국 내 검색 결과가 없습니다. 주소를 다시 확인해 주세요.")
            except:
                st.error("연결 지연: 잠시 후 다시 시도하세요.")

        # 검색 결과가 있을 경우 선택 창 표시
        if st.session_state.search_results:
            res_map = {r.address: r for r in st.session_state.search_results}
            sel_res_addr = st.selectbox("정확한 위치를 선택하세요", list(res_map.keys()))
            
            # 💡 [핵심] 지도에서 먼저 확인하도록 유도
            if st.button("📍 지도에서 위치 확인"):
                target = res_map[sel_res_addr]
                is_area = target.raw.get('type') in ['administrative', 'suburb', 'city_district']
                
                st.session_state.temp_loc = {
                    "lat": target.latitude, "lon": target.longitude, 
                    "name": sel_res_addr.split(',')[0].strip(),
                    "full_addr": sel_res_addr,
                    "is_area": is_area,
                    "geojson": target.raw.get('geojson') if is_area else None
                }
                st.session_state.map_center = [target.latitude, target.longitude]
                st.session_state.map_zoom = 14 if is_area else 17
                st.rerun()

        # 3️⃣ 최종 선점 (위치를 확인한 후에만 나타남)
        if st.session_state.temp_loc:
            st.markdown("---")
            t = st.session_state.temp_loc
            tag = "[동네] " if t.get('is_area') else ""
            st.info(f"지도에 표시된 '{tag}{t['name']}' 위치가 맞나요?")
            
            if st.button(f"🚩 최종 선점하기!", use_container_width=True):
                save_val = f"{selected_owner} | {tag}{t['name']}"
                payload = {"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}
                requests.post(API_URL, data=json.dumps(payload))
                st.session_state.temp_loc = None
                st.session_state.search_results = []
                st.success("영업권 선점이 완료되었습니다!")
                st.rerun()

# =========================================================
# 🗺️ 메인 화면: 실시간 관제 지도
# =========================================================
st.title("🗺️ 소중한밥상 실시간 관제 시스템")

m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

# 등록된 데이터 지도에 표시
for _, row in df.iterrows():
    if row['lat'] != 0:
        try:
            full_owner_info = str(row['owner'])
            owner_only = full_owner_info.split('|')[0].strip()
            color = "red" if owner_only == selected_owner else "blue"
            
            # 동네는 1000m, 일반 아파트/주소는 100m 반경 표시
            radius_val = 1000 if "[동네]" in full_owner_info else 100
            
            folium.Marker([row['lat'], row['lon']], popup=full_owner_info, icon=folium.Icon(color=color)).add_to(m)
            folium.Circle(location=[row['lat'], row['lon']], radius=radius_val, color=color, fill=True, fill_opacity=0.15).add_to(m)
        except: continue

# 작업 중인 임시 위치 및 구역 표시 (초록색)
if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    if t.get('is_area') and t.get('geojson'):
        # 동네일 경우 실제 경계선 표시
        folium.GeoJson(t['geojson'], style_function=lambda x: {'fillColor': '#2ecc71', 'color': '#27ae60', 'weight': 2, 'fillOpacity': 0.3}).add_to(m)
    else:
        # 일반 주소일 경우 100m 원 표시
        folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
        folium.Circle(location=[t['lat'], t['lon']], radius=100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
