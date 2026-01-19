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
        
        /* 🌟 [추가] 통합 플로팅 대시보드 스타일 (숫자 + 버튼 세트) */
        .floating-dashboard {
            position: fixed; top: 20px; right: 80px; z-index: 999999;
            display: flex; align-items: center; gap: 15px;
            background: rgba(255, 255, 255, 0.95); padding: 8px 20px;
            border-radius: 40px; border: 2.5px solid #FF4B4B;
            box-shadow: 0 6px 20px rgba(0,0,0,0.2);
        }
        .stat-item { font-size: 14px; font-weight: 800; color: #333; white-space: nowrap; }
    </style>
    """, unsafe_allow_html=True)

# ⚠️ 사장님 마스터코딩 정보 (URL 유지)
API_URL = "https://script.google.com/macros/s/AKfycbyBZSNYE4mE0YKRvdp4GYjMLeJmwzBIGs3-EmJ2bBNr-yu-fazKw6wFodx_ypM5M2RT/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79" 
SONGDO_HQ = [37.385, 126.654] # 인천 송도 본사 좌표

# --- 🛠️ 세션 상태 초기화 (마스터코딩 동일) ---
if 'df' not in st.session_state: st.session_state.df = pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
if 'map_center' not in st.session_state: st.session_state.map_center = SONGDO_HQ
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'confirm_delete_id' not in st.session_state: st.session_state.confirm_delete_id = None
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

# --- [추가] 📊 통계 데이터 미리 계산 ---
total_df = st.session_state.df
owners_cnt = len(set([str(val).split('|')[0].strip() for val in total_df['owner'] if str(val).strip() and val != 'owner']))
branches_cnt = len(set(["|".join(str(val).split('|')[:2]).strip() for val in total_df['owner'] if "|" in str(val)]))

def simplify_name(n):
    c = n.replace("[지점]", "").replace("[동네]", "").strip()
    return c.split(",")[0].strip() if "," in c else c

def analyze_radius_type(query):
    area_keywords = ['동', '읍', '면', '리']
    if any(k in query for k in area_keywords): return 1000
    return 200

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

# --- 사이드바 (마스터코딩 100% 유지) ---
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    if st.button("🔄 최근 데이터 가져오기", use_container_width=True):
        st.session_state.df = fetch_data(API_URL); st.rerun()

    st.header("👤 점주 관리")
    with st.expander("➕ 신규 점주 등록"):
        new_o_name = st.text_input("새 점주 성함", key="new_o")
        if st.button("점주 영구 등록"):
            if new_o_name:
                requests.post(API_URL, data=json.dumps({"action": "add", "owner": new_o_name, "address": "신규등록", "lat": 0, "lon": 0}))
                st.session_state.df = fetch_data(API_URL); st.rerun()

    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in st.session_state.df['owner'] if name.strip() and name != 'owner'])))
    st.write("---")
    selected_owner = st.selectbox("1️⃣ 관리할 점주 선택", ["선택"] + unique_owners)
    
    selected_branch = "선택"
    if selected_owner != "선택":
        col_oe, col_od = st.columns(2)
        if col_oe.button(f"📝 이름수정", key="btn_oe"): st.session_state.edit_owner = True
        if col_od.button(f"❌ 점주삭제", key="btn_od"): st.session_state.delete_owner = True

        if st.session_state.get('edit_owner'):
            new_on = st.text_input(f"'{selected_owner}'님의 새 성함")
            if st.button("수정 완료", key="confirm_oe"):
                requests.post(API_URL, data=json.dumps({"action": "rename_owner_entirely", "old_name": selected_owner, "new_name": new_on}))
                st.session_state.edit_owner = False; st.session_state.df = fetch_data(API_URL); st.rerun()

        if st.session_state.get('delete_owner'):
            st.warning(f"'{selected_owner}'님과 하위 데이터를 삭제할까요?")
            if st.button("네, 전체 삭제합니다", key="confirm_od"):
                requests.post(API_URL, data=json.dumps({"action": "delete_owner_entirely", "owner_name": selected_owner}))
                st.session_state.delete_owner = False; st.session_state.df = fetch_data(API_URL); st.rerun()

        st.write("---")
        with st.expander("➕ 신규 지점 추가"):
            new_b = st.text_input(f"'{selected_owner}'님의 새 지점명")
            if st.button("지점 추가 확정"):
                if new_b:
                    requests.post(API_URL, data=json.dumps({"action": "add", "owner": f"{selected_owner} | {new_b}", "address": "지점선등록", "lat": 0, "lon": 0}))
                    st.session_state.df = fetch_data(API_URL); st.rerun()

        owner_data_raw = st.session_state.df[st.session_state.df['owner'].str.contains(f"^{selected_owner}\s*\|", na=False)]
        branches = sorted(list(set([val.split('|')[1].strip() for val in owner_data_raw['owner'] if len(val.split('|')) >= 2])))
        selected_branch = st.selectbox("2️⃣ 관리할 지점 선택", ["선택"] + branches)
        
        if selected_branch != "선택":
            col_be, col_bd = st.columns(2)
            if col_be.button(f"📝 지점수정", key="btn_be"): st.session_state.edit_branch = True
            if col_bd.button(f"❌ 지점삭제", key="btn_bd"): st.session_state.delete_branch = True

            if st.session_state.get('edit_branch'):
                new_bn = st.text_input(f"'{selected_branch}'의 새 이름")
                if st.button("지점 수정 완료"):
                    requests.post(API_URL, data=json.dumps({"action": "rename_branch_entirely", "owner_name": selected_owner, "old_branch_name": selected_branch, "new_branch_name": new_bn}))
                    st.session_state.edit_branch = False; st.session_state.df = fetch_data(API_URL); st.rerun()

            if st.session_state.get('delete_branch'):
                st.warning(f"'{selected_branch}' 지점의 모든 구역을 삭제할까요?")
                if st.button("네, 지점 삭제합니다"):
                    requests.post(API_URL, data=json.dumps({"action": "delete_branch_entirely", "owner_name": selected_owner, "branch_name": selected_branch}))
                    st.session_state.delete_branch = False; st.session_state.df = fetch_data(API_URL); st.rerun()

            st.write("---")
            st.markdown(f"#### 🏘️ {selected_branch} 구역 리스트")
            branch_data = owner_data_raw[owner_data_raw['owner'].str.contains(f"\|\s*{selected_branch}\s*\|", na=False)]
            for idx, row in branch_data[branch_data['lat'] != 0].iterrows():
                short_name = simplify_name(row['owner'].split('|')[-1].strip())
                c1, c2 = st.columns([4, 1])
                if c1.button(f"🏠 {short_name}", key=f"go_{idx}", use_container_width=True):
                    st.session_state.map_center = [row['lat'], row['lon']]; st.rerun()
                if c2.button("❌", key=f"del_{idx}"):
                    st.session_state.confirm_delete_id = idx; st.rerun()

    st.markdown("---")
    st.header("3️⃣ 영업권 신규 선점")
    if selected_branch != "선택":
        st.success(f"📍 등록 지점: **{selected_branch}**")
        target_branch = selected_branch
    else: target_branch = st.text_input("등록할 지점명 (예: 송도1점)")
    
    search_addr = st.text_input("아파트/동네/도로명 입력", key="s_box")
    if st.button("🔍 위치 확인", use_container_width=True):
        if search_addr:
            res = get_location_alternative(search_addr)
            if res: st.session_state.search_results = res; st.session_state.map_center = [res[0]['lat'], res[0]['lon']]; st.rerun()

# --- 🗺️ 메인 지도 및 통합 플로팅 대시보드 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")

# 🌟 [추가] 숫자 통계와 버튼이 함께 움직이는 통합 대시보드
st.markdown(f"""
    <div class="floating-dashboard">
        <span class="stat-item">👤 점주: {owners_cnt}명</span>
        <span style="color: #ddd; font-weight: 300;">|</span>
        <span class="stat-item">🏢 지점: {branches_cnt}개</span>
    </div>
    """, unsafe_allow_html=True)

# 🌟 [추가] 통계 바 옆에 배치되는 다운로드 버튼 (레이아웃 조절)
with st.container():
    c_empty, c_btn = st.columns([8.2, 1.8])
    with c_btn:
        csv_data = total_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 엑셀(CSV) 다운로드",
            data=csv_data,
            file_name='소중한밥상_운영현황.csv',
            mime='text/csv',
            use_container_width=True,
            key="float_excel_btn"
        )

m = folium.Map(location=st.session_state.map_center, zoom_start=15)

# 1. 기존 데이터 표시 (가변 반경 적용)
for _, row in st.session_state.df.iterrows():
    if row['lat'] != 0:
        owner_name = str(row['owner']).split('|')[0].strip()
        color = "red" if owner_name == selected_owner else "blue"
        rad = 1000 if "[동네]" in str(row['owner']) else 200
        folium.Marker([row['lat'], row['lon']], icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=rad, color=color, fill=True, fill_opacity=0.1).add_to(m)

# 2. 별 띄우기 (임시 위치) 표시
if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="orange", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=t['radius'], color="orange", fill=True, fill_opacity=0.2, dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key="main_map")
