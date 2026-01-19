import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정 및 디자인 (사장님 디자인 100% 유지)
st.set_page_config(page_title="소중한밥상 통합 관제 시스템", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
        [data-testid="stSidebar"] { background-color: #FFF0F0; }
        [data-testid="stSidebarCollapsedControl"] svg { display: none !important; }
        [data-testid="stSidebarCollapsedControl"] {
            background-color: #FF4B4B !important; color: white !important;
            border-radius: 0 15px 15px 0 !important; width: 160px !important; height: 65px !important;
            display: flex !important; align-items: center !important; justify-content: center !important;
            position: fixed !important; left: 0 !important; top: 20px !important;
            box-shadow: 5px 5px 15px rgba(0,0,0,0.5) !important; z-index: 1000000 !important; cursor: pointer !important;
        }
        [data-testid="stSidebarCollapsedControl"]::after {
            content: "🆑 클릭해서 메뉴열기" !important;
            font-weight: 900 !important; color: white !important; font-size: 17px !important; white-space: nowrap !important;
        }
    </style>
    """, unsafe_allow_html=True)

# ⚠️ 사장님 고유 정보
API_URL = "https://script.google.com/macros/s/AKfycbw4MGFNridXvxj906TWMp0v37lcB-aAl-EWwC2ellpS98Kgm5k5jda4zRyaIHFDpKtB/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79" 

# --- 최적화된 데이터 로드 함수 ---
def fetch_data(api_url):
    """구글 시트에서 데이터를 새로 가져옵니다."""
    try:
        response = requests.get(api_url, allow_redirects=True, timeout=10)
        data = response.json()
        df = pd.DataFrame(data[1:], columns=data[0])
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

# 세션 상태 초기화 (데이터 캐싱용)
if 'df' not in st.session_state:
    st.session_state.df = fetch_data(API_URL)
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None

# 지명 간소화 로직
def simplify_name(full_name):
    clean = full_name.replace("[지점]", "").replace("[동네]", "").strip()
    if "," in clean: clean = clean.split(",")[0].strip()
    return clean

# 검색 엔진 로직 유지
def get_location_alternative(query):
    results = []
    try:
        geolocator = Nominatim(user_agent="sojunghan_bapsang_manager")
        locations = geolocator.geocode(query, exactly_one=False, limit=5, country_codes='kr')
        if locations:
            for loc in locations:
                is_area = any(x in query for x in ["동", "읍", "면", "리"])
                results.append({"display_name": f"{'[동네] ' if is_area else '[지점] '} {loc.address}", "lat": loc.latitude, "lon": loc.longitude, "is_area": is_area})
    except: pass
    if not results:
        headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        try:
            res = requests.get(f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}", headers=headers, timeout=3).json()
            for d in res.get('documents', []):
                is_area = any(x in query for x in ["동", "읍", "면", "리"])
                results.append({"display_name": f"{'[동네] ' if is_area else '[지점] '} {d['place_name']} ({d['address_name']})", "lat": float(d['y']), "lon": float(d['x']), "is_area": is_area})
        except: pass
    return results

# --- 사이드바 ---
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # 상단에 데이터 새로고침 버튼 (필요할 때만 수동으로)
    if st.button("🔄 전체 데이터 새로고침", use_container_width=True):
        st.session_state.df = fetch_data(API_URL)
        st.rerun()

    st.header("👤 점주 관리")
    with st.expander("➕ 신규 점주 등록"):
        new_name = st.text_input("새 점주 성함")
        if st.button("점주 영구 등록"):
            if new_name:
                payload = {"action": "add", "owner": new_name, "address": "신규등록", "lat": 0, "lon": 0}
                requests.post(API_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
                # 등록 성공 후 데이터 강제 업데이트
                st.session_state.df = fetch_data(API_URL)
                st.success("등록 완료!"); time.sleep(1); st.rerun()

    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in st.session_state.df['owner'] if name.strip() and name != 'owner'])))
    st.write("---")
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    if selected_owner != "선택":
        st.markdown("---")
        st.header("📍 선점 내역")
        owner_data = st.session_state.df[st.session_state.df['owner'].str.contains(f"^{selected_owner}\s*\|", na=False)]
        
        if not owner_data.empty:
            pts = owner_data[~owner_data['owner'].str.contains("\[동네\]")]
            neighborhoods = owner_data[owner_data['owner'].str.contains("\[동네\]")]

            if not pts.empty:
                st.markdown("##### 📍 개별 지점 (100m)")
                for idx, row in pts.iterrows():
                    short_display = simplify_name(row['owner'].split('|')[-1].strip())
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        if st.button(f"🏠 {short_display}", key=f"goto_{idx}", use_container_width=True):
                            st.session_state.map_center = [row['lat'], row['lon']]; st.rerun()
                    with col2:
                        if st.button("❌", key=f"del_{idx}"):
                            requests.post(API_URL, data=json.dumps({"action": "delete", "row_index": int(idx) + 2}))
                            st.session_state.df = fetch_data(API_URL) # 삭제 후 즉시 로드
                            st.rerun()

            if not neighborhoods.empty:
                st.write("")
                st.markdown("##### 🏘️ 동네 구역 (1km)")
                for idx, row in neighborhoods.iterrows():
                    short_display = simplify_name(row['owner'].split('|')[-1].strip())
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        if st.button(f"🏠 {short_display}", key=f"goto_{idx}", use_container_width=True):
                            st.session_state.map_center = [row['lat'], row['lon']]; st.rerun()
                    with col2:
                        if st.button("❌", key=f"del_{idx}"):
                            requests.post(API_URL, data=json.dumps({"action": "delete", "row_index": int(idx) + 2}))
                            st.session_state.df = fetch_data(API_URL) # 삭제 후 즉시 로드
                            st.rerun()
        else: st.info("선점한 구역이 없습니다.")

    st.markdown("---")
    st.header("2️⃣ 영업권 구역 선점")
    search_addr = st.text_input("아파트명 또는 주소 입력", key="search_input_box")
    
    if st.button("🔍 위치 찾기", use_container_width=True):
        if search_addr:
            results = get_location_alternative(search_addr)
            if results:
                st.session_state.search_results = results
                st.session_state.map_center = [results[0]['lat'], results[0]['lon']]; st.rerun()
            else: st.error("주소를 찾을 수 없습니다.")

    if st.session_state.search_results:
        res_options = { r['display_name']: r for r in st.session_state.search_results }
        sel = st.selectbox("정확한 위치를 선택하세요", list(res_options.keys()))
        if st.button("📍 위치 확인"):
            st.session_state.temp_loc = res_options[sel]
            st.session_state.map_center = [st.session_state.temp_loc['lat'], st.session_state.temp_loc['lon']]; st.rerun()

    if st.session_state.temp_loc and selected_owner != "선택":
        st.write("---")
        t = st.session_state.temp_loc
        radius_m = 1000 if t['is_area'] else 100
        if st.button(f"🚩 선점하기 (반경 {radius_m}m)", use_container_width=True):
            is_overlap = False
            new_pos = (t['lat'], t['lon'])
            for _, row in st.session_state.df.iterrows():
                if row['lat'] != 0:
                    if str(row['owner']).split('|')[0].strip() == selected_owner: continue
                    dist = geodesic(new_pos, (row['lat'], row['lon'])).meters
                    existing_radius = 1000 if "[동네]" in str(row['owner']) else 100
                    if dist < (radius_m + existing_radius) / 2: is_overlap = True; break
            if is_overlap: st.error("중첩되는 구역이 있습니다.")
            else:
                prefix = "[동네] " if t['is_area'] else "[지점] "
                save_val = f"{selected_owner} | {prefix}{simplify_name(t['display_name'])}"
                payload = {"action": "add", "owner": save_val, "address": t['display_name'], "lat": t['lat'], "lon": t['lon']}
                requests.post(API_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
                st.session_state.df = fetch_data(API_URL) # 선점 후 즉시 로드
                st.session_state.temp_loc = None; st.rerun()

# --- 메인 지도 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")



m = folium.Map(location=st.session_state.map_center, zoom_start=15)

# 세션에 저장된 데이터로 지도 표시 (매번 시트를 읽지 않음)
for _, row in st.session_state.df.iterrows():
    if row['lat'] != 0:
        owner_name = str(row['owner']).split('|')[0].strip()
        color = "red" if owner_name == selected_owner else "blue"
        r = 1000 if "[동네]" in str(row['owner']) else 100
        folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=r, color=color, fill=True, fill_opacity=0.1).add_to(m)

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    r = 1000 if t['is_area'] else 100
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=r, color="green", fill=False, dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
