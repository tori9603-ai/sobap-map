import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="소중한밥상 통합 관제 시스템", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
        [data-testid="stSidebar"] { background-color: #FFF0F0; }
        [data-testid="stSidebarCollapsedControl"] {
            background-color: #FF4B4B !important; color: white !important;
            border-radius: 0 15px 15px 0 !important; width: 160px !important; height: 65px !important;
            display: flex !important; align-items: center !important; justify-content: center !important;
            position: fixed !important; left: 0 !important; top: 20px !important;
            box-shadow: 5px 5px 15px rgba(0,0,0,0.5) !important; z-index: 1000000 !important; cursor: pointer !important;
        }
        [data-testid="stSidebarCollapsedControl"]::after {
            content: "🆑 메뉴열기" !important; font-weight: 900 !important; color: white !important; font-size: 17px !important;
        }
    </style>
    """, unsafe_allow_html=True)

# ⚠️ 사장님 마스터코딩 정보
API_URL = "https://script.google.com/macros/s/AKfycbwyveXED04ihVIn8TjJOkiLrlY4vCZVAY_g7SbGbQ5ndKPFzeYPA7kbU8h4SBiQoG9S/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79" 
SONGDO_HQ = [37.385, 126.654] 

# --- 세션 상태 초기화 (오류 방지 및 별 띄우기 동기화 핵심) ---
if 'df' not in st.session_state: st.session_state.df = pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
if 'map_center' not in st.session_state: st.session_state.map_center = SONGDO_HQ
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'overlap_error' not in st.session_state: st.session_state.overlap_error = None
if 'prev_owner' not in st.session_state: st.session_state.prev_owner = "선택"

def fetch_data(api_url):
    try:
        response = requests.get(api_url, allow_redirects=True, timeout=10)
        data = response.json()
        df = pd.DataFrame(data[1:], columns=data[0])
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

if st.session_state.df.empty: st.session_state.df = fetch_data(API_URL)

def simplify_name(n):
    c = n.replace("[지점]", "").replace("[동네]", "").strip()
    return c.split(",")[0].strip() if "," in c else c

# ⭐ 주소 유형에 따른 반경 분석 로직 (1km / 200m)
def analyze_radius_type(query):
    area_keywords = ['동', '읍', '면', '리']
    if any(k in query for k in area_keywords):
        return 1000  # 동네 단위 1km
    return 200  # 상세 주소 200m

def get_location_alternative(query):
    results = []
    radius = analyze_radius_type(query)
    is_area = (radius == 1000)
    try:
        geolocator = Nominatim(user_agent="sojunghan_bapsang_manager")
        locations = geolocator.geocode(query, exactly_one=False, limit=5, country_codes='kr')
        if locations:
            for loc in locations:
                results.append({"display_name": f"{'[동네] ' if is_area else '[지점] '} {loc.address}", "lat": loc.latitude, "lon": loc.longitude, "is_area": is_area, "radius": radius})
    except: pass
    if not results:
        headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        try:
            res = requests.get(f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}", headers=headers, timeout=3).json()
            for d in res.get('documents', []):
                results.append({"display_name": f"{'[동네] ' if is_area else '[지점] '} {d['place_name']} ({d['address_name']})", "lat": float(d['y']), "lon": float(d['x']), "is_area": is_area, "radius": radius})
        except: pass
    return results

# --- 사이드바 ---
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    if st.button("🔄 최근 데이터 가져오기", use_container_width=True):
        st.session_state.df = fetch_data(API_URL); st.rerun()

    # 1. 점주 관리 영역
    st.header("👤 점주 관리")
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in st.session_state.df['owner'] if name.strip() and name != 'owner'])))
    selected_owner = st.selectbox("1️⃣ 관리할 점주 선택", ["선택"] + unique_owners)
    
    selected_branch = "선택"
    if selected_owner != "선택":
        # 2. 지점 관리 영역
        st.write("---")
        owner_data_raw = st.session_state.df[st.session_state.df['owner'].str.contains(f"^{selected_owner}\s*\|", na=False)]
        branches = sorted(list(set([val.split('|')[1].strip() for val in owner_data_raw['owner'] if len(val.split('|')) >= 2])))
        selected_branch = st.selectbox("2️⃣ 관리할 지점 선택", ["선택"] + branches)
        
        if selected_branch != "선택":
            st.write("---")
            st.markdown(f"#### 🏘️ {selected_branch} 구역 리스트")
            branch_data = owner_data_raw[owner_data_raw['owner'].str.contains(f"\|\s*{selected_branch}\s*\|", na=False)]
            for idx, row in branch_data.iterrows():
                short_name = simplify_name(row['owner'].split('|')[-1].strip())
                c1, c2 = st.columns([4, 1])
                if c1.button(f"🏠 {short_name}", key=f"go_{idx}", use_container_width=True):
                    st.session_state.map_center = [row['lat'], row['lon']]; st.rerun()
                if c2.button("❌", key=f"del_{idx}"):
                    requests.post(API_URL, data=json.dumps({"action": "delete", "row_index": int(idx) + 2}))
                    st.session_state.df = fetch_data(API_URL); st.rerun()

    # 3. 영업권 신규 선점
    st.markdown("---")
    st.header("3️⃣ 영업권 신규 선점")
    if selected_branch != "선택":
        st.success(f"📍 등록 지점: **{selected_branch}**")
        target_branch = selected_branch
    else:
        target_branch = st.text_input("등록할 지점명 (예: 송도1점)")
    
    search_addr = st.text_input("아파트/동네/도로명 입력", key="s_box")
    if st.button("🔍 위치 확인", use_container_width=True):
        if search_addr:
            res = get_location_alternative(search_addr)
            if res: st.session_state.search_results = res; st.session_state.map_center = [res[0]['lat'], res[0]['lon']]; st.rerun()

    if st.session_state.search_results:
        res_opts = { r['display_name']: r for r in st.session_state.search_results }
        sel = st.selectbox("정확한 위치 선택", list(res_opts.keys()))
        if st.button("📍 별 띄우기"):
            target = res_opts[sel]
            st.session_state.temp_loc = target
            st.session_state.map_center = [target['lat'], target['lon']]
            
            # 중복 체크 (가변 반경 반영)
            new_r = target['radius']
            blocking = None
            for _, row in st.session_state.df.iterrows():
                if row['lat'] != 0:
                    curr_owner = str(row['owner']).split('|')[0].strip()
                    if curr_owner == selected_owner: continue
                    dist = geodesic((target['lat'], target['lon']), (row['lat'], row['lon'])).meters
                    exist_r = 1000 if "[동네]" in str(row['owner']) else 200
                    if dist < (new_r + exist_r): blocking = curr_owner; break
            st.session_state.overlap_error = f"❌ 등록 불가: {blocking} 점주님과 겹칩니다." if blocking else None
            st.rerun()

    if st.session_state.temp_loc and selected_owner != "선택":
        if st.session_state.get('overlap_error'): st.error(st.session_state.overlap_error)
        else:
            t = st.session_state.temp_loc
            if st.button(f"🚩 {selected_owner} | {target_branch} 등록", use_container_width=True):
                full_val = f"{selected_owner} | {target_branch} | {'[동네] ' if t['is_area'] else '[지점] '}{simplify_name(t['display_name'])}"
                requests.post(API_URL, data=json.dumps({"action": "add", "owner": full_val, "address": t['display_name'], "lat": t['lat'], "lon": t['lon']}))
                st.session_state.df = fetch_data(API_URL); st.session_state.temp_loc = None; st.rerun()

# --- 메인 지도 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")
m = folium.Map(location=st.session_state.map_center, zoom_start=15)

# 1. 기존 데이터 표시
for _, row in st.session_state.df.iterrows():
    if row['lat'] != 0:
        owner_part = str(row['owner']).split('|')[0].strip()
        color = "red" if owner_part == selected_owner else "blue"
        rad = 1000 if "[동네]" in str(row['owner']) else 200
        folium.Marker([row['lat'], row['lon']], icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=rad, color=color, fill=True, fill_opacity=0.1).add_to(m)

# 2. 별 띄우기 (임시 위치) 표시
if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="orange", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=t['radius'], color="orange", fill=True, fill_opacity=0.2, dash_array='5, 5').add_to(m)

map_out = st_folium(m, width="100%", height=800, key="main_map")

# 지도 클릭 시 별 위치 이동
if map_out and map_out.get('last_clicked') and st.session_state.temp_loc:
    st.session_state.temp_loc['lat'] = map_out['last_clicked']['lat']
    st.session_state.temp_loc['lon'] = map_out['last_clicked']['lng']
    st.rerun()
