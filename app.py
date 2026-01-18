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
st.set_page_config(page_title="소중한밥상 영업권 관리", layout="wide")

# ⚠️ 사장님의 웹 앱 URL (A:owner, B:address, C:lat, D:lon 순서용)
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

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [37.5665, 126.9780]
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = 11
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []

# =========================================================
# 🍱 사이드바: 동네 및 지점 통합 관리
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # 1️⃣ 점주 선택
    st.header("1️⃣ 점주 선택")
    raw_owners = df['owner'].unique().tolist()
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in raw_owners if name.strip()])))
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    with st.expander("➕ 신규 점주 등록"):
        add_name = st.text_input("새 점주 성함")
        if st.button("시트에 등록"):
            if add_name:
                payload = {"action": "add", "owner": add_name, "address": "신규등록", "lat": 0, "lon": 0}
                requests.post(API_URL, data=json.dumps(payload))
                st.success("등록 완료!")
                st.rerun()

    st.markdown("---")

    if selected_owner != "선택":
        # 📍 현재 선점 목록
        st.header("📍 선점 목록")
        owner_data = df[(df['owner'].str.contains(selected_owner, na=False)) & (df['lat'] != 0)]
        if not owner_data.empty:
            for idx, row in owner_data.iterrows():
                # 장소 이름 표시 (동네인지 아파트인지 구분 표시 포함)
                place_name = str(row['owner']).split('|')[-1].strip()
                c1, c2 = st.columns([4, 1])
                with c1:
                    if st.button(f"🏠 {place_name}", key=f"mv_{idx}"):
                        st.session_state.map_center = [row['lat'], row['lon']]
                        st.session_state.map_zoom = 15 if "[동네]" in place_name else 17
                        st.rerun()
                with c2:
                    if st.button("❌", key=f"rm_{idx}"):
                        new_df = df.drop(idx)
                        requests.post(API_URL, data=json.dumps({"action": "sync", "data": [new_df.columns.tolist()] + new_df.values.tolist()}))
                        st.rerun()
        
        st.markdown("---")

        # 2️⃣ 새 장소/동네 검색
        st.header("2️⃣ 주소 및 동네 검색")
        search_addr = st.text_input("예: 암남동, 롯데캐슬")
        if st.button("🔍 검색"):
            try:
                random_agent = f"sobap_area_{int(time.time())}"
                geolocator = Nominatim(user_agent=random_agent)
                # 💡 geometry='geojson'으로 구역 정보를 가져옵니다.
                res = geolocator.geocode(search_addr, exactly_one=False, timeout=15, geometry='geojson')
                if res: st.session_state.search_results = res
                else: st.warning("결과 없음")
            except: st.error("연결 지연: 잠시 후 다시 시도하세요.")

        if st.session_state.search_results:
            res_map = {r.address: r for r in st.session_state.search_results}
            sel_res = st.selectbox("정확한 곳을 선택하세요", list(res_map.keys()))
            
            if st.button("📍 위치 및 구역 확인"):
                t = res_map[sel_res]
                # 💡 행정구역(동네)인지 확인
                is_area = t.raw.get('type') in ['administrative', 'suburb', 'city_district']
                
                st.session_state.temp_loc = {
                    "lat": t.latitude, "lon": t.longitude, 
                    "name": sel_res.split(',')[0].strip(),
                    "full_addr": sel_res,
                    "is_area": is_area,
                    "geojson": t.raw.get('geojson') if is_area else None
                }
                st.session_state.map_center = [t.latitude, t.longitude]
                st.session_state.map_zoom = 14 if is_area else 17
                st.rerun()

        # 3️⃣ 최종 선점
        if st.session_state.temp_loc:
            t = st.session_state.temp_loc
            tag = "[동네] " if t['is_area'] else ""
            if st.button(f"🚩 {tag}'{t['name']}' 선점!", use_container_width=True):
                # 💡 동네 선점 시 이름에 [동네] 태그를 붙여 저장합니다.
                save_val = f"{selected_owner} | {tag}{t['name']}"
                payload = {"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}
                requests.post(API_URL, data=json.dumps(payload))
                st.session_state.temp_loc = None
                st.success("선점 완료!")
                st.rerun()

# =========================================================
# 🗺️ 메인 화면: 지도 (범위 가변형)
# =========================================================
st.title("🗺️ 소중한밥상 실시간 영업권 지도")

m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

for _, row in df.iterrows():
    if row['lat'] != 0:
        try:
            full_owner = str(row['owner'])
            owner_only = full_owner.split('|')[0].strip()
            color = "red" if owner_only == selected_owner else "blue"
            
            # 💡 [핵심] 이름에 '[동네]'가 포함되어 있으면 반경을 1000M로, 아니면 100M로 설정
            radius_val = 1000 if "[동네]" in full_owner else 100
            
            folium.Marker([row['lat'], row['lon']], popup=full_owner, icon=folium.Icon(color=color)).add_to(m)
            folium.Circle(location=[row['lat'], row['lon']], radius=radius_val, color=color, fill=True, fill_opacity=0.15).add_to(m)
        except: continue

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    # 검색 중일 때 동네면 경계선(Polygon) 표시, 아니면 100m 원 표시
    if t['is_area'] and t['geojson']:
        folium.GeoJson(t['geojson'], style_function=lambda x: {'fillColor': '#2ecc71', 'color': '#27ae60', 'weight': 2, 'fillOpacity': 0.3}).add_to(m)
    else:
        folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
        folium.Circle(location=[t['lat'], t['lon']], radius=100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
