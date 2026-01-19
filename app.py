import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정 및 성능 최적화
st.set_page_config(
    page_title="소중한밥상 통합 관제 시스템", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🔑 관제 센터 전용 암호
ACCESS_PASSWORD = "0119" 

# 💡 [UI] 사이드바 및 🆑 클릭 버튼 스타일
st.markdown("""
    <style>
        [data-testid="stSidebar"] { background-color: #FFF0F0; }
        [data-testid="stSidebarCollapsedControl"] {
            background-color: #FF4B4B !important; color: white !important;
            border-radius: 0 15px 15px 0 !important;
            width: 160px !important; height: 65px !important;
            display: flex !important; align-items: center !important;
            justify-content: center !important; position: fixed !important;
            left: 0 !important; top: 20px !important;
            box-shadow: 5px 5px 15px rgba(0,0,0,0.5) !important;
            z-index: 1000000 !important;
            cursor: pointer !important;
        }
        [data-testid="stSidebarCollapsedControl"] svg { display: none !important; }
        [data-testid="stSidebarCollapsedControl"]::after {
            content: "🆑 클릭해서 메뉴열기" !important;
            font-weight: 900 !important; color: white !important;
            font-size: 17px !important; white-space: nowrap !important;
        }
    </style>
    """, unsafe_allow_html=True)

# --- 🔐 로그인 로직 ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 소중한밥상 관제 센터 접속")
    input_pw = st.text_input("접속 암호", type="password")
    if st.button("접속하기"):
        if input_pw == ACCESS_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("암호가 올바르지 않습니다.")
    st.stop()

# ⚠️ [사장님 확인 필요] 사장님이 주신 최신 주소입니다.
API_URL = "https://script.google.com/macros/s/AKfycbyMAJv4dHq42kRRHLkDwoGph6wctjYQu4az9_3zfW54XNCJ8sK3SGpUDsT0kOZZv9fr/exec"
# ⚠️ [카카오 확인] 카카오 API 키 (Local 서비스가 활성화되어 있어야 합니다)
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79" 

@st.cache_data(ttl=60)
def get_data_cached(api_url):
    try:
        response = requests.get(api_url, allow_redirects=True, timeout=10)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df['owner'] = df['owner'].astype(str).str.strip()
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            return df[~df['owner'].isin(['0', '', 'nan'])]
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
    except Exception as e:
        st.sidebar.error(f"구글 시트 연동 실패: {e}")
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

# 💡 [핵심] 검색 결과가 없을 때 상세 원인을 보여주는 스마트 검색 함수
@st.cache_data(ttl=3600)
def get_location_smart_debug(query, api_key):
    headers = {"Authorization": f"KakaoAK {api_key}"}
    all_results = []
    try:
        # 1. 주소 검색 시도
        res_addr_raw = requests.get(f"https://dapi.kakao.com/v2/local/search/address.json?query={query}", headers=headers, timeout=5)
        if res_addr_raw.status_code == 401:
            st.error("🚨 카카오 API 키가 올바르지 않거나 권한이 없습니다. (401 에러)")
            return []
        
        res_addr = res_addr_raw.json()
        if res_addr.get('documents'):
            for d in res_addr['documents']:
                d['display_name'] = f"[주소] {d['address_name']}"
                d['is_area'] = d.get('address_type') == 'REGION'
                all_results.append(d)
        
        # 2. 키워드 검색 시도
        res_kw = requests.get(f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}", headers=headers, timeout=5).json()
        if res_kw.get('documents'):
            for d in res_kw['documents']:
                d['display_name'] = f"[{d.get('category_group_name', '장소')}] {d['place_name']} ({d['address_name']})"
                d['is_area'] = False
                all_results.append(d)
                
    except Exception as e:
        st.error(f"검색 엔진 통신 오류: {e}")
    return all_results

def parse_detailed_address(address_str):
    if not address_str or address_str == "대한민국": return "지정 위치"
    parts = [p.strip() for p in address_str.split(',')]
    filtered_parts = [p for p in parts if p != "대한민국"]
    return filtered_parts[0] if filtered_parts else "지정 위치"

def clear_cache(): st.cache_data.clear()

df = get_data_cached(API_URL)

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
        search_addr = st.text_input("아파트명 또는 주소 입력 (예: 행촌로 14)")
        
        if st.button("🔍 위치 찾기", use_container_width=True):
            # 진단 기능이 추가된 검색 실행
            results = get_location_smart_debug(search_addr, KAKAO_API_KEY)
            if results:
                st.session_state.search_results = results
                st.session_state.map_center = [float(results[0]['y']), float(results[0]['x'])]
                st.rerun()
            else:
                st.warning("유사한 주소를 찾을 수 없습니다. API 키 설정이나 주소 형식을 확인해 주세요.")

        if st.session_state.get('search_results'):
            res_options = { r['display_name']: r for r in st.session_state.search_results }
            sel_name = st.selectbox("가장 유사한 장소를 선택하세요", list(res_options.keys()))
            
            if st.button("📍 선택한 위치로 핀 이동"):
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
                        if row_owner_only == selected_owner: continue
                        dist = geodesic(new_pos, (row['lat'], row['lon'])).meters
                        existing_radius = 1000 if "[동네]" in str(row['owner']) else 100
                        if dist < (new_radius + existing_radius):
                            is_overlap = True; break
                if is_overlap:
                    st.error("해당 구역은 이미 다른 점주님이 선점하였습니다.")
                else:
                    save_val = f"{selected_owner} | {('[동네] ' if t.get('is_area', False) else '')}{t['name']}"
                    requests.post(API_URL, data=json.dumps({"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}))
                    st.session_state.temp_loc = None
                    st.session_state.search_results = []
                    clear_cache(); st.rerun()

# --- 메인 화면: 실시간 지도 ---
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

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
