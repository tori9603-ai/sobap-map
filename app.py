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
st.set_page_config(page_title="소중한밥상 통합 관제 센터", layout="wide")

# ⚠️ 사장님의 최신 구글 웹 앱 URL (A:owner, B:address, C:lat, D:lon 순서 최적화)
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
            # 무의미한 데이터 필터링 (0이나 nan 제외)
            df = df[~df['owner'].isin(['0', '', 'nan'])]
            return df
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
    except:
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

df = get_data()

# --- 세션 상태 관리 ---
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756] # 부산 시청 기준 시작
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = 11
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []

# =========================================================
# 🍱 왼쪽 사이드바: 100% 한국 전용 관리 시스템
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # 1️⃣ 점주 관리
    st.header("1️⃣ 점주 관리")
    raw_owners = df['owner'].astype(str).tolist()
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in raw_owners if name.strip()])))
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    with st.expander("➕ 신규 점주 등록"):
        add_name = st.text_input("새 점주 성함")
        if st.button("시트에 영구 등록"):
            if add_name:
                requests.post(API_URL, data=json.dumps({"action": "add", "owner": add_name, "address": "신규등록", "lat": 0, "lon": 0}))
                st.success(f"'{add_name}' 등록 완료! 새로고침 하세요.")
                st.rerun()

    st.markdown("---")

    if selected_owner != "선택":
        # 📍 선점 내역 리스트 (장소 이름 중심)
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

        # 2️⃣ 새 장소 검색 (한국 전용 & 동네/아파트 통합)
        st.header("2️⃣ 영업권 위치 잡기")
        search_type = st.radio("위치 지정 방식", ["주소/아파트/동네 검색", "지도에서 직접 클릭"])
        
        if search_type == "주소/아파트/동네 검색":
            search_addr = st.text_input("예: 암남동, 해운대 롯데캐슬, 중동 123-4")
            if st.button("🔍 한국 주소 찾기"):
                try:
                    # 💡 [핵심] country_codes='kr' 설정을 통해 한국 주소만 검색합니다.
                    random_agent = f"sobap_final_{int(time.time())}"
                    geolocator = Nominatim(user_agent=random_agent)
                    res = geolocator.geocode(search_addr, exactly_one=False, timeout=15, country_codes='kr', geometry='geojson')
                    if res:
                        st.session_state.search_results = res
                    else:
                        st.warning("한국 내 검색 결과가 없습니다.")
                except:
                    st.error("연결 지연: 잠시 후 다시 시도하세요.")
            
            if st.session_state.search_results:
                res_map = {r.address: r for r in st.session_state.search_results}
                sel_res_addr = st.selectbox("정확한 위치를 선택하세요", list(res_map.keys()))
                
                if st.button("📍 선택한 곳 구역 확인"):
                    target = res_map[sel_res_addr]
                    # 동네(행정구역)인지 판단
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
        else:
            st.info("지도에서 원하는 곳을 클릭하면 초록색 별이 생깁니다.")

        # 3️⃣ 최종 선점
        if st.session_state.temp_loc:
            st.markdown("---")
            t = st.session_state.temp_loc
            tag = "[동네] " if t.get('is_area') else ""
            if st.button(f"🚩 {tag}'{t['name']}' 최종 선점!", use_container_width=True):
                # 저장 형식: '점주명 | [동네] 장소명'
                save_val = f"{selected_owner} | {tag}{t['name']}"
                payload = {"action": "add", "owner": save_val, "address": t.get('full_addr', '직접지정'), "lat": t['lat'], "lon": t['lon']}
                requests.post(API_URL, data=json.dumps(payload))
                st.session_state.temp_loc = None
                st.success("영업권 선점 완료!")
                st.rerun()

# =========================================================
# 🗺️ 메인 화면: 스마트 영업권 관제 지도
# =========================================================
st.title("🗺️ 소중한밥상 실시간 관제 시스템 (한국)")

m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

# 지도 클릭 이벤트 (직접 클릭 모드일 때만 작동)
map_data = st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")

if map_data.get("last_clicked") and search_type == "지도에서 직접 클릭":
    c_lat, c_lon = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
    if not st.session_state.temp_loc or (st.session_state.temp_loc['lat'] != c_lat):
        st.session_state.temp_loc = {"lat": c_lat, "lon": c_lon, "name": "직접 지정 위치", "is_area": False}
        st.rerun()

# 등록된 데이터 지도에 표시
for _, row in df.iterrows():
    if row['lat'] != 0:
        try:
            full_owner = str(row['owner'])
            owner_only = full_owner.split('|')[0].strip()
            color = "red" if owner_only == selected_owner else "blue"
            
            # 동네는 1000m, 일반 주소는 100m 반경 표시
            radius_val = 1000 if "[동네]" in full_owner else 100
            
            folium.Marker([row['lat'], row['lon']], popup=full_owner, icon=folium.Icon(color=color)).add_to(m)
            folium.Circle(location=[row['lat'], row['lon']], radius=radius_val, color=color, fill=True, fill_opacity=0.15).add_to(m)
        except: continue

# 작업 중인 임시 위치 표시
if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    if t.get('is_area') and t.get('geojson'):
        folium.GeoJson(t['geojson'], style_function=lambda x: {'fillColor': '#2ecc71', 'color': '#27ae60', 'weight': 2, 'fillOpacity': 0.3}).add_to(m)
    else:
        folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
        folium.Circle(location=[t['lat'], t['lon']], radius=100, color="green", dash_array='5, 5').add_to(m)
