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
st.set_page_config(page_title="소중한밥상 통합 관제 시스템", layout="wide")

# ⚠️ 사장님 고유 정보
API_URL = "https://script.google.com/macros/s/AKfycbxDw8kU3K2LzcaM0zOStvwBdsZs98zyjNzQtgxJlRnZcjTCA70RUEQMLmg4lHTCb9uQ/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79"

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

def get_location_smart(query):
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    try:
        res = requests.get(f"https://dapi.kakao.com/v2/local/search/address.json?query={query}", headers=headers, timeout=5)
        if res.status_code == 200 and res.json().get('documents'):
            docs = res.json()['documents']
            for d in docs: d['is_area'] = d.get('address_type') == 'REGION'
            return docs, "✅ 카카오 검색 성공"
    except: pass
    try:
        geolocator = Nominatim(user_agent=f"sobap_master_final_{int(time.time())}")
        res = geolocator.geocode(f"{query}, 대한민국", exactly_one=False, timeout=10)
        if res:
            results = [{"address_name": r.address, "y": r.latitude, "x": r.longitude, 
                        "is_area": r.raw.get('class') in ['boundary', 'place'] and r.raw.get('type') in ['administrative', 'suburb', 'city_district']} for r in res]
            return results, "⚠️ 비상용 엔진 사용 중"
    except: pass
    return [], "❓ 검색 결과가 없습니다."

df = get_data()

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'prev_selected_owner' not in st.session_state: st.session_state.prev_selected_owner = "선택"

with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    st.header("👤 점주 관리")
    
    with st.expander("➕ 신규 점주 등록"):
        new_name = st.text_input("새 점주 성함")
        if st.button("점주 영구 등록"):
            if new_name:
                requests.post(API_URL, data=json.dumps({"action": "add", "owner": new_name, "address": "신규등록", "lat": 0, "lon": 0}))
                st.rerun()

    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in df['owner'] if name.strip()])))
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    # 점주 변경 시 자동 지도 이동 로직
    if selected_owner != st.session_state.prev_selected_owner:
        st.session_state.prev_selected_owner = selected_owner
        if selected_owner != "선택":
            target_data = df[(df['owner'].str.contains(selected_owner, na=False)) & (df['lat'] != 0)]
            if not target_data.empty:
                st.session_state.map_center = [target_data.iloc[0]['lat'], target_data.iloc[0]['lon']]
                st.rerun()

    if selected_owner != "선택":
        st.markdown("---")
        st.header("📍 현재 선점 내역")
        owner_data = df[(df['owner'].str.contains(selected_owner, na=False)) & (df['lat'] != 0)]
        if not owner_data.empty:
            for idx, row in owner_data.iterrows():
                place_display = str(row['owner']).split('|')[-1].strip()
                col1, col2 = st.columns([4, 1])
                with col1:
                    if st.button(f"🏠 {place_display}", key=f"mv_{idx}"):
                        st.session_state.map_center = [row['lat'], row['lon']]
                        st.rerun()
                with col2:
                    if st.button("❌", key=f"rm_{idx}"):
                        new_df = df.drop(idx)
                        requests.post(API_URL, data=json.dumps({"action": "sync", "data": [new_df.columns.tolist()] + new_df.values.tolist()}))
                        st.rerun()

        st.markdown("---")
        st.header("2️⃣ 영업권 구역 선점")
        st.info("💡 팁: 지도를 클릭하면 핀 위치와 주소가 자동으로 업데이트됩니다.")
        search_addr = st.text_input("동네 이름 또는 아파트명")
        if st.button("🔍 위치 찾기"):
            results, status = get_location_smart(search_addr)
            if results:
                st.session_state.search_results = results
                st.info(status)
            else: st.warning(status)

        if st.session_state.search_results:
            res_options = { r['address_name']: r for r in st.session_state.search_results }
            sel_res_addr = st.selectbox("위치 선택", list(res_options.keys()))
            if st.button("📍 지도 확인"):
                target = res_options[sel_res_addr]
                st.session_state.temp_loc = {
                    "lat": float(target['y']), "lon": float(target['x']),
                    "is_area": target.get('is_area', False), "full_addr": sel_res_addr,
                    "name": sel_res_addr.split(' ')[-1] if not target.get('is_area', False) else sel_res_addr.split(',')[0].strip()
                }
                st.session_state.map_center = [float(target['y']), float(target['x'])]
                st.rerun()

        if st.session_state.temp_loc:
            t = st.session_state.temp_loc
            area_tag = "[동네] " if t.get('is_area', False) else ""
            st.warning(f"🏠 선택된 주소: {t['full_addr']}") # 💡 사용자 확인용
            
            if st.button("🚩 해당 주소 선점하기", use_container_width=True):
                is_overlap = False
                new_radius = 1000 if t.get('is_area', False) else 100
                for _, row in df.iterrows():
                    if row['lat'] != 0:
                        dist = geodesic((t['lat'], t['lon']), (row['lat'], row['lon'])).meters
                        if dist < (new_radius + (1000 if "[동네]" in str(row['owner']) else 100)):
                            is_overlap = True
                            break
                if is_overlap:
                    st.error("이미 선점된 구역과 겹칩니다!")
                else:
                    save_val = f"{selected_owner} | {area_tag}{t['name']}"
                    requests.post(API_URL, data=json.dumps({"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}))
                    st.session_state.temp_loc = None
                    st.rerun()

# --- 메인 화면: 지도 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")
m = folium.Map(location=st.session_state.map_center, zoom_start=15)

for _, row in df.iterrows():
    if row['lat'] != 0:
        full_info = str(row['owner'])
        owner_name = full_info.split('|')[0].strip()
        color = "red" if owner_name == selected_owner else "blue"
        folium.Marker([row['lat'], row['lon']], popup=full_info, icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=1000 if "[동네]" in full_info else 100, color=color, fill=True, fill_opacity=0.15).add_to(m)

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=1000 if t.get('is_area', False) else 100, color="green", dash_array='5, 5').add_to(m)

map_data = st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")

# 💡 [핵심] 지도 클릭 시 역지오코딩 로직
if map_data.get("last_clicked") and st.session_state.temp_loc:
    clicked_lat = map_data["last_clicked"]["lat"]
    clicked_lon = map_data["last_clicked"]["lng"]
    
    # 지점의 실제 주소 찾아오기 (역지오코딩)
    try:
        geolocator = Nominatim(user_agent=f"sobap_reverse_{int(time.time())}")
        location = geolocator.reverse((clicked_lat, clicked_lon), language='ko')
        if location:
            new_addr = location.address
            # 주소에서 핵심 명칭(동네 또는 건물명) 추출
            addr_parts = [p.strip() for p in new_addr.split(',')]
            # 보통 한국 주소의 경우 뒷부분이 더 큰 단위이므로 앞부분의 구체적 명칭 사용
            display_name = addr_parts[0] if len(addr_parts) > 0 else "지정 위치"
        else:
            new_addr = "직접 지정 주소"
            display_name = "지정 위치"
    except:
        new_addr = "주소 변환 실패"
        display_name = "지정 위치"

    # 세션 상태 업데이트
    st.session_state.temp_loc["lat"] = clicked_lat
    st.session_state.temp_loc["lon"] = clicked_lon
    st.session_state.temp_loc["full_addr"] = new_addr
    st.session_state.temp_loc["name"] = display_name
    st.rerun()
