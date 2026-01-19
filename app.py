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

# 💡 [CSS] 사이드바 디자인 및 클릭 버튼 커스텀 (사장님 디자인 유지)
st.markdown("""
    <style>
        [data-testid="stSidebar"] { background-color: #FFF0F0; }
        [data-testid="stSidebarCollapsedControl"] svg { display: none !important; }
        [data-testid="stSidebarCollapsedControl"] {
            background-color: #FF4B4B !important;
            color: white !important;
            border-radius: 0 15px 15px 0 !important;
            width: 160px !important;
            height: 65px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            position: fixed !important;
            left: 0 !important;
            top: 20px !important;
            box-shadow: 5px 5px 15px rgba(0,0,0,0.5) !important;
            z-index: 1000000 !important;
            cursor: pointer !important;
        }
        [data-testid="stSidebarCollapsedControl"]::after {
            content: "🆑 클릭해서 메뉴열기" !important;
            font-weight: 900 !important;
            color: white !important;
            font-size: 17px !important;
            white-space: nowrap !important;
        }
    </style>
    """, unsafe_allow_html=True)

# ⚠️ [수정완료] 사장님이 새로 복사해주신 구글 앱스 스크립트 URL 반영
API_URL = "https://script.google.com/macros/s/AKfycbw4MGFNridXvxj906TWMp0v37lcB-aAl-EWwC2ellpS98Kgm5k5jda4zRyaIHFDpKtB/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79" # REST API 키
KAKAO_JS_KEY = "919179e81cdd52922456fbef112f964a"  # JavaScript 키

# 데이터 불러오기 함수 (캐싱 적용)
@st.cache_data(ttl=5)
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
    except:
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

# 주소 검색 및 좌표 변환 (카카오 로컬 API)
@st.cache_data(ttl=3600)
def get_location_smart(query, api_key):
    headers = {"Authorization": f"KakaoAK {api_key}"}
    all_results = []
    try:
        # 주소 검색
        res_addr = requests.get(f"https://dapi.kakao.com/v2/local/search/address.json?query={query}", headers=headers, timeout=3).json()
        if res_addr.get('documents'):
            for d in res_addr['documents']:
                d['display_name'] = d['address_name']
                d['is_area'] = d.get('address_type') == 'REGION'
                all_results.append(d)
        # 키워드(아파트명 등) 검색
        res_kw = requests.get(f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}", headers=headers, timeout=3).json()
        if res_kw.get('documents'):
            for d in res_kw['documents']:
                d['display_name'] = f"[{d.get('category_group_name', '장소')}] {d['place_name']} ({d['address_name']})"
                d['is_area'] = False
                all_results.append(d)
    except: pass
    return all_results

def parse_detailed_address(address_str):
    if not address_str or address_str == "대한민국": return "지정 위치"
    parts = [p.strip() for p in address_str.split(',')]
    filtered_parts = [p for p in parts if p != "대한민국"]
    return filtered_parts[0] if filtered_parts else "지정 위치"

def clear_cache():
    st.cache_data.clear()

# 데이터 로드
df = get_data_cached(API_URL)

# 세션 상태 초기화
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'prev_selected_owner' not in st.session_state: st.session_state.prev_selected_owner = "선택"

# --- 사이드바 구성 ---
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    st.header("👤 점주 관리")
    
    # 신규 점주 등록
    with st.expander("➕ 신규 점주 등록"):
        new_name = st.text_input("새 점주 성함")
        if st.button("점주 영구 등록", use_container_width=True):
            if new_name:
                payload = {"action": "add", "owner": new_name, "address": "신규등록", "lat": 0, "lon": 0}
                headers = {'Content-Type': 'application/json'}
                try:
                    # [중요] 구글 스크립트로 데이터 전송
                    res = requests.post(API_URL, data=json.dumps(payload), headers=headers, timeout=10)
                    if res.status_code == 200:
                        st.success(f"✅ {new_name} 등록 요청 성공!")
                        clear_cache()
                        time.sleep(1.5) # 시트 기록 시간 확보
                        st.rerun()
                    else: st.error(f"서버 응답 오류: {res.status_code}")
                except Exception as e: st.error(f"연결 실패: {e}")
            else: st.warning("성함을 입력해주세요.")

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
                    # 삭제 로직 (필요 시 구현)
                    pass

        st.markdown("---")
        st.header("2️⃣ 영업권 구역 선점")
        search_addr = st.text_input("아파트명 또는 주소 입력")
        
        if st.button("🔍 위치 찾기", use_container_width=True):
            if search_addr:
                results = get_location_smart(search_addr, KAKAO_API_KEY)
                if results:
                    st.session_state.search_results = results
                    first = results[0]
                    st.session_state.map_center = [float(first['y']), float(first['x'])]
                    st.rerun()
                else: st.error("검색 결과가 없습니다.")

        if st.session_state.get('search_results'):
            res_options = { r['display_name']: r for r in st.session_state.search_results }
            sel_name = st.selectbox("정확한 장소를 선택하세요", list(res_options.keys()))
            if st.button("📍 선택한 위치 확인"):
                target = res_options[sel_name]
                st.session_state.temp_loc = {
                    "lat": float(target['y']), "lon": float(target['x']),
                    "is_area": target.get('is_area', False),
                    "full_addr": target.get('address_name') or sel_name,
                    "name": parse_detailed_address(sel_name)
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
                        if str(row['owner']).split('|')[0].strip() == selected_owner: continue
                        dist = geodesic(new_pos, (row['lat'], row['lon'])).meters
                        existing_radius = 1000 if "[동네]" in str(row['owner']) else 100
                        if dist < (new_radius + existing_radius):
                            is_overlap = True; break
                
                if is_overlap: st.error("이미 다른 점주님이 선점한 지역입니다.")
                else:
                    save_val = f"{selected_owner} | {('[동네] ' if t.get('is_area', False) else '')}{t['name']}"
                    payload = {"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}
                    requests.post(API_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
                    st.session_state.temp_loc = None
                    clear_cache(); st.rerun()

# --- 메인 화면: 실시간 지도 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")

m = folium.Map(location=st.session_state.map_center, zoom_start=15)

# 기존 마커 표시
for _, row in df.iterrows():
    if row['lat'] != 0:
        owner_name = str(row['owner']).split('|')[0].strip()
        color = "red" if owner_name == selected_owner else "blue"
        folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=1000 if "[동네]" in str(row['owner']) else 100, color=color, fill=True, fill_opacity=0.15).add_to(m)

# 임시 위치 마커
if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=1000 if t.get('is_area', False) else 100, color="green", dash_array='5, 5').add_to(m)

# 지도 출력
st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center[0]}_{st.session_state.map_center[1]}")
