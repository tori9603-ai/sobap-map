import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정 및 성능 최적화 (💡 사이드바 기본 열림 유지)
st.set_page_config(
    page_title="소중한밥상 통합 관제 시스템", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 💡 [핵심] 사이드바 화살표 버튼 옆에 '사이드바' 글자 강제 삽입 CSS
st.markdown("""
    <style>
        /* 1. 사이드바 배경색 (연한 빨강 유지) */
        [data-testid="stSidebar"] {
            background-color: #FFF0F0;
        }
        
        /* 2. 사이드바 열기 버튼 스타일 (글자 추가 및 시인성 강화) */
        [data-testid="stSidebarCollapsedControl"] {
            background-color: #FF4B4B !important; /* 진한 빨강 배경 */
            color: white !important;
            border-radius: 0 10px 10px 0 !important;
            width: 140px !important; /* 글자가 들어갈 수 있게 가로 길이 확보 */
            height: 55px !important; /* 버튼 높이 조정 */
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            position: fixed !important;
            left: 0 !important;
            top: 25px !important;
            box-shadow: 4px 4px 12px rgba(0,0,0,0.4) !important;
            z-index: 9999999 !important;
        }
        
        /* 화살표 아이콘 크기 조정 */
        [data-testid="stSidebarCollapsedControl"] svg {
            fill: white !important;
            width: 28px !important;
            height: 28px !important;
        }
        
        /* 💡 사장님 요청: 화살표 옆에 '사이드바' 글자 추가 */
        [data-testid="stSidebarCollapsedControl"]::after {
            content: " 사이드바" !important;
            font-weight: 800 !important;
            color: white !important;
            font-size: 18px !important;
            margin-left: 5px !important;
            white-space: nowrap !important;
        }
    </style>
    """, unsafe_allow_html=True)

# ⚠️ 사장님 고유 정보 (유지)
API_URL = "https://script.google.com/macros/s/AKfycbxDw8kU3K2LzcaM0zOStvwBdsZs98zyjNzQtgxJlRnZcjTCA70RUEQMLmg4lHTCb9uQ/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79"

# 터보 데이터 캐싱 (유지)
@st.cache_data(ttl=60)
def get_data_cached(api_url):
    try:
        response = requests.get(api_url, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df['owner'] = df['owner'].astype(str).str.strip()
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            return df[~df['owner'].isin(['0', '', 'nan'])]
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
    except:
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

# 주소 파싱 (대한민국 제거 로직 유지)
def parse_detailed_address(address_str):
    if not address_str or address_str == "대한민국":
        return "지정 위치"
    parts = [p.strip() for p in address_str.split(',')]
    filtered_parts = [p for p in parts if p != "대한민국"]
    return filtered_parts[0] if filtered_parts else "지정 위치"

# 스마트 검색 엔진 (유사 리스트 유지)
@st.cache_data(ttl=3600)
def get_location_smart(query, api_key):
    headers = {"Authorization": f"KakaoAK {api_key}"}
    all_results = []
    try:
        res_addr = requests.get(f"https://dapi.kakao.com/v2/local/search/address.json?query={query}", headers=headers, timeout=3).json()
        if res_addr.get('documents'):
            for d in res_addr['documents']:
                d['display_name'] = d['address_name']
                d['is_area'] = d.get('address_type') == 'REGION'
                all_results.append(d)
        res_kw = requests.get(f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}", headers=headers, timeout=3).json()
        if res_kw.get('documents'):
            for d in res_kw['documents']:
                d['display_name'] = f"[{d.get('category_group_name', '장소')}] {d['place_name']} ({d['address_name']})"
                d['is_area'] = False
                all_results.append(d)
    except: pass
    return all_results

def clear_cache():
    st.cache_data.clear()

df = get_data_cached(API_URL)

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'prev_selected_owner' not in st.session_state: st.session_state.prev_selected_owner = "선택"

# --- 사이드바 관리 메뉴 ---
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    st.header("👤 점주 관리")
    
    with st.expander("➕ 신규 점주 등록"):
        new_name = st.text_input("새 점주 성함")
        if st.button("점주 영구 등록"):
            if new_name:
                requests.post(API_URL, data=json.dumps({"action": "add", "owner": new_name, "address": "신규등록", "lat": 0, "lon": 0}))
                clear_cache(); st.rerun()

    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in df['owner'] if name.strip()])))
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    if selected_owner != st.session_state.prev_selected_owner:
        st.session_state.prev_selected_owner = selected_owner
        if selected_owner != "선택":
            target_data = df[(df['owner'].str.contains(selected_owner, na=False)) & (df['lat'] != 0)]
            if not target_data.empty:
                st.session_state.map_center = [target_data.iloc[0]['lat'], target_data.iloc[0]['lon']]
                st.rerun()

    if selected_owner != "선택":
        st.markdown("---")
        st.header("📍 선점 내역")
        owner_data = df[(df['owner'].str.contains(selected_owner, na=False)) & (df['lat'] != 0)]
        for idx, row in owner_data.iterrows():
            place_display = str(row['owner']).split('|')[-1].strip()
            c1, c2 = st.columns([4, 1])
            with c1:
                if st.button(f"🏠 {place_display}", key=f"mv_{idx}"):
                    st.session_state.map_center = [row['lat'], row['lon']]
                    st.rerun()
            with c2:
                if st.button("❌", key=f"rm_{idx}"):
                    new_df = df.drop(idx)
                    requests.post(API_URL, data=json.dumps({"action": "sync", "data": [new_df.columns.tolist()] + new_df.values.tolist()}))
                    clear_cache(); st.rerun()

        st.markdown("---")
        st.header("2️⃣ 영업권 구역 선점")
        search_addr = st.text_input("아파트명 또는 주소 입력")
        
        if st.button("🔍 위치 찾기", use_container_width=True):
            results = get_location_smart(search_addr, KAKAO_API_KEY)
            if results:
                st.session_state.search_results = results
                first = results[0]
                st.session_state.map_center = [float(first['y']), float(first['x'])]
                st.rerun()

        if st.session_state.get('search_results'):
            res_options = { r['display_name']: r for r in st.session_state.search_results }
            sel_name = st.selectbox("정확한 장소를 선택하세요", list(res_options.keys()))
            if st.button("📍 선택한 위치 확인"):
                target = res_options[sel_name]
                detailed_name = parse_detailed_address(sel_name)
                st.session_state.temp_loc = {
                    "lat": float(target['y']), "lon": float(target['x']),
                    "is_area": target.get('is_area', False),
                    "full_addr": target.get('address_name') or sel_name,
                    "name": detailed_name
                }
                st.session_state.map_center = [float(target['y']), float(target['x'])]
                st.rerun()

        if st.session_state.temp_loc:
            t = st.session_state.temp_loc
            if st.button("🚩 해당 주소 선점하기", use_container_width=True):
                is_overlap = False
                new_radius = 1000 if t.get('is_area', False) else 100
                new_pos = (t['lat'], t['lon'])

                for _, row in df.iterrows():
                    if row['lat'] != 0:
                        row_owner_only = str(row['owner']).split('|')[0].strip()
                        # 본인 중복 선점은 허용
                        if row_owner_only == selected_owner: continue
                        dist = geodesic(new_pos, (row['lat'], row['lon'])).meters
                        existing_radius = 1000 if "[동네]" in str(row['owner']) else 100
                        if dist < (new_radius + existing_radius):
                            is_overlap = True; break
                
                if is_overlap:
                    st.error("해당 아파트는 다른 점주님이 이미 선점 하였습니다")
                else:
                    save_val = f"{selected_owner} | {('[동네] ' if t.get('is_area', False) else '')}{t['name']}"
                    requests.post(API_URL, data=json.dumps({"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}))
                    st.session_state.temp_loc = None
                    clear_cache(); st.rerun()

# --- 메인 화면 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")
m = folium.Map(location=st.session_state.map_center, zoom_start=15)

for _, row in df.iterrows():
    if row['lat'] != 0:
        owner_name = str(row['owner']).split('|')[0].strip()
        color = "red" if owner_name == selected_owner else "blue"
        folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=1000 if "[동네]" in str(row['owner']) else 100, color=color, fill=True, fill_opacity=0.15).add_to(m)

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=1000 if t.get('is_area', False) else 100, color="green", dash_array='5, 5').add_to(m)

map_data = st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}", returned_objects=["last_clicked"])

# 지도 클릭 시 미세 조정 및 상세 지명 자동 추출 (속도 유지)
if map_data and map_data.get("last_clicked") and st.session_state.temp_loc:
    c_lat, c_lon = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
    if round(st.session_state.temp_loc["lat"], 5) != round(c_lat, 5):
        try:
            geolocator = Nominatim(user_agent=f"sobap_final_ui_v6_{int(time.time())}")
            location = geolocator.reverse((c_lat, c_lon), language='ko')
            full_addr = location.address if location else f"좌표: {c_lat:.4f}"
            detailed_name = parse_detailed_address(full_addr)
        except:
            full_addr = f"좌표: {c_lat:.4f}"; detailed_name = "지정 위치"

        st.session_state.temp_loc.update({"lat": c_lat, "lon": c_lon, "full_addr": full_addr, "name": detailed_name})
        st.rerun()
