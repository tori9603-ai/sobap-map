import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정 및 디자인 (마스터코딩 고유 디자인 유지)
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
        /* 지도 위 오버레이 스타일 */
        .map-stats {
            position: absolute; top: 10px; right: 50px; z-index: 1000;
            background: rgba(255, 255, 255, 0.85); padding: 8px 12px;
            border: 1px solid #FF4B4B; border-radius: 8px;
            font-size: 13px; font-weight: bold; color: #333;
            box-shadow: 2px 2px 6px rgba(0,0,0,0.2);
        }
    </style>
    """, unsafe_allow_html=True)

# ⚠️ 사장님 마스터코딩 정보 (최신 URL 유지)
API_URL = "https://script.google.com/macros/s/AKfycbyBZSNYE4mE0YKRvdp4GYjMLeJmwzBIGs3-EmJ2bBNr-yu-fazKw6wFodx_ypM5M2RT/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79" 
SONGDO_HQ = [37.385, 126.654] #

# --- 세션 상태 초기화 ---
if 'df' not in st.session_state: st.session_state.df = pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
if 'map_center' not in st.session_state: st.session_state.map_center = SONGDO_HQ
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'confirm_delete_id' not in st.session_state: st.session_state.confirm_delete_id = None
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

# --- 📊 통계 계산 (지도 상단 표시용) ---
total_df = st.session_state.df
owners_cnt = len(set([str(val).split('|')[0].strip() for val in total_df['owner'] if str(val).strip() and val != 'owner']))
branches_cnt = len(set(["|".join(str(val).split('|')[:2]).strip() for val in total_df['owner'] if "|" in str(val)]))

def simplify_name(n):
    c = n.replace("[지점]", "").replace("[동네]", "").strip()
    return c.split(",")[0].strip() if "," in c else c

def get_location_alternative(query):
    area_keywords = ['동', '읍', '면', '리']
    is_area = any(k in query for k in area_keywords)
    radius = 1000 if is_area else 200 # 사장님 요청 200m 반영
    results = []
    try:
        geolocator = Nominatim(user_agent="sojunghan_bapsang_manager")
        locations = geolocator.geocode(query, exactly_one=False, limit=5, country_codes='kr')
        if locations:
            for loc in locations:
                results.append({"display_name": f"{'[동네] ' if is_area else '[지점] '} {loc.address}", "lat": loc.latitude, "lon": loc.longitude, "is_area": is_area, "radius": radius})
    except: pass
    return results

# --- 사이드바 ---
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    if st.button("🔄 최근 데이터 가져오기", use_container_width=True):
        st.session_state.df = fetch_data(API_URL); st.rerun()

    # 보고서 다운로드 기능 (매각 준비용)
    st.header("📥 보고서 관리")
    csv = total_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(label="📄 전체 운영현황 CSV 다운로드", data=csv, file_name='소중한밥상_전체현황.csv', mime='text/csv', use_container_width=True)

    # 1. 점주 관리
    st.write("---")
    st.header("👤 점주 관리")
    unique_owners = sorted(list(set([str(val).split('|')[0].strip() for val in total_df['owner'] if str(val).strip() and val != 'owner'])))
    selected_owner = st.selectbox("1️⃣ 관리할 점주 선택", ["선택"] + unique_owners)
    
    selected_branch = "선택"
    if selected_owner != "선택":
        owner_data_raw = total_df[total_df['owner'].str.contains(f"^{selected_owner}\s*\|", na=False)]
        branches = sorted(list(set([val.split('|')[1].strip() for val in owner_data_raw['owner'] if len(val.split('|')) >= 2])))
        selected_branch = st.selectbox("2️⃣ 관리할 지점 선택", ["선택"] + branches)
        
        if selected_branch != "선택":
            st.markdown(f"#### 🏘️ {selected_branch} 리스트")
            branch_data = owner_data_raw[owner_data_raw['owner'].str.contains(f"\|\s*{selected_branch}\s*\|", na=False)]
            for idx, row in branch_data[branch_data['lat'] != 0].iterrows():
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
    target_branch = selected_branch if selected_branch != "선택" else st.text_input("등록할 지점명")
    search_addr = st.text_input("아파트/동네/도로명 입력", key="s_box")
    if st.button("🔍 위치 확인", use_container_width=True):
        if search_addr:
            res = get_location_alternative(search_addr)
            if res: st.session_state.search_results = res; st.session_state.map_center = [res[0]['lat'], res[0]['lon']]; st.rerun()

    if st.session_state.search_results:
        res_opts = { r['display_name']: r for r in st.session_state.search_results }
        sel = st.selectbox("정확한 위치 선택", list(res_opts.keys()))
        if st.button("📍 별 띄우기"):
            target = res_opts[sel]; st.session_state.temp_loc = target; st.session_state.map_center = [target['lat'], target['lon']]; st.rerun()

    if st.session_state.temp_loc and selected_owner != "선택":
        t = st.session_state.temp_loc
        if st.button(f"🚩 {selected_owner} | {target_branch} 등록", use_container_width=True):
            full_val = f"{selected_owner} | {target_branch} | {'[동네] ' if t['is_area'] else '[지점] '}{simplify_name(t['display_name'])}"
            requests.post(API_URL, data=json.dumps({"action": "add", "owner": full_val, "address": t['display_name'], "lat": t['lat'], "lon": t['lon']}))
            st.session_state.df = fetch_data(API_URL); st.session_state.temp_loc = None; st.rerun()

# --- 메인 지도 및 오른쪽 상단 통계 오버레이 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")

# 🌟 [벽돌 추가] 지도 우측 상단 숫자 오버레이
st.markdown(f"""
    <div class="map-stats">
        👤 점주: {owners_cnt}명 | 🏢 지점: {branches_cnt}개
    </div>
    """, unsafe_allow_html=True)

m = folium.Map(location=st.session_state.map_center, zoom_start=15)

# 기존 데이터 표시 (가변 반경 적용)
for _, row in total_df.iterrows():
    if row['lat'] != 0:
        owner_name = str(row['owner']).split('|')[0].strip()
        color = "red" if owner_name == selected_owner else "blue"
        rad = 1000 if "[동네]" in str(row['owner']) else 200
        folium.Marker([row['lat'], row['lon']], icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=rad, color=color, fill=True, fill_opacity=0.1).add_to(m)

# 별 띄우기 표시
if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="orange", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=t['radius'], color="orange", fill=True, fill_opacity=0.2, dash_array='5, 5').add_to(m)

map_out = st_folium(m, width="100%", height=800, key="main_map")

# 지도 클릭 시 별 위치 이동
if map_out and map_out.get('last_clicked') and st.session_state.temp_loc:
    st.session_state.temp_loc['lat'] = map_out['last_clicked']['lat']
    st.session_state.temp_loc['lon'] = map_out['last_clicked']['lng']; st.rerun()
