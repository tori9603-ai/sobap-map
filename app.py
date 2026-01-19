import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정 및 디자인 (사장님 디자인 절대 유지)
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

# ⚠️ 사장님 고유 정보 유지
API_URL = "https://script.google.com/macros/s/AKfycbw4MGFNridXvxj906TWMp0v37lcB-aAl-EWwC2ellpS98Kgm5k5jda4zRyaIHFDpKtB/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79" 

# 검색 엔진 로직 유지 (Nominatim + Kakao 하이브리드)
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

@st.cache_data(ttl=5)
def get_data_cached(api_url):
    try:
        response = requests.get(api_url, allow_redirects=True)
        data = response.json()
        df = pd.DataFrame(data[1:], columns=data[0])
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

df = get_data_cached(API_URL)

if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None

# --- 사이드바 ---
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    st.header("👤 점주 관리")
    
    with st.expander("➕ 신규 점주 등록"):
        new_name = st.text_input("새 점주 성함")
        if st.button("점주 영구 등록"):
            if new_name:
                payload = {"action": "add", "owner": new_name, "address": "신규등록", "lat": 0, "lon": 0}
                requests.post(API_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
                st.success("등록 완료!"); st.cache_data.clear(); time.sleep(1); st.rerun()

    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in df['owner'] if name.strip() and name != 'owner'])))
    st.write("---")
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    # ⭐ [추가 기능] 선점 내역 리스트 (삭제 및 수정 버튼)
    if selected_owner != "선택":
        st.markdown("---")
        st.header("📍 선점 내역")
        # 해당 점주의 데이터만 필터링 (정규식으로 정확히 점주 이름만 체크)
        owner_data = df[df['owner'].str.contains(f"^{selected_owner}\s*\|", na=False)]
        
        if not owner_data.empty:
            for idx, row in owner_data.iterrows():
                # '점주명 | [타입] 장소명' 에서 장소명만 추출
                display_name = row['owner'].split('|')[-1].strip()
                
                # 가로로 이름, 수정, 삭제 버튼 배치
                col1, col2, col3 = st.columns([2.5, 1, 1])
                with col1:
                    if st.button(f"🏠 {display_name}", key=f"goto_{idx}", use_container_width=True):
                        st.session_state.map_center = [row['lat'], row['lon']]
                        st.rerun()
                with col2:
                    if st.button("📝", key=f"edit_btn_{idx}", help="이름 수정"):
                        st.session_state.edit_idx = idx
                with col3:
                    if st.button("❌", key=f"del_btn_{idx}", help="삭제"):
                        # 구글 시트에서 삭제 (행 번호 전송: 데이터프레임 인덱스 + 2)
                        delete_payload = {"action": "delete", "row_index": int(idx) + 2}
                        requests.post(API_URL, data=json.dumps(delete_payload))
                        st.toast(f"{display_name} 삭제 중...")
                        st.cache_data.clear(); time.sleep(1); st.rerun()

            # 수정 모드 활성화 시 입력창 표시
            if 'edit_idx' in st.session_state:
                edit_row = df.loc[st.session_state.edit_idx]
                st.info(f"선택한 구역: {edit_row['owner'].split('|')[-1].strip()}")
                new_place_name = st.text_input("새로운 아파트/동네 이름 입력")
                if st.button("이름 변경 완료"):
                    if new_place_name:
                        # 기존 타입([지점]/[동네]) 유지하며 이름만 교체
                        type_prefix = "[동네] " if "[동네]" in edit_row['owner'] else "[지점] "
                        updated_owner = f"{selected_owner} | {type_prefix}{new_place_name}"
                        update_payload = {"action": "update", "row_index": int(st.session_state.edit_idx) + 2, "new_owner": updated_owner}
                        requests.post(API_URL, data=json.dumps(update_payload))
                        del st.session_state.edit_idx
                        st.cache_data.clear(); time.sleep(1); st.rerun()

    st.markdown("---")
    st.header("2️⃣ 영업권 구역 선점")
    search_addr = st.text_input("아파트명 또는 주소 입력", key="search_input_box")
    
    if st.button("🔍 위치 찾기", use_container_width=True):
        if search_addr:
            results = get_location_alternative(search_addr)
            if results:
                st.session_state.search_results = results
                st.session_state.map_center = [results[0]['lat'], results[0]['lon']]
                st.rerun()
            else: st.error("주소를 찾을 수 없습니다.")

    if st.session_state.search_results:
        res_options = { r['display_name']: r for r in st.session_state.search_results }
        sel = st.selectbox("정확한 위치를 선택하세요", list(res_options.keys()))
        if st.button("📍 위치 확인"):
            st.session_state.temp_loc = res_options[sel]
            st.session_state.map_center = [st.session_state.temp_loc['lat'], st.session_state.temp_loc['lon']]
            st.rerun()

    if st.session_state.temp_loc and selected_owner != "선택":
        st.write("---")
        t = st.session_state.temp_loc
        radius_m = 1000 if t['is_area'] else 100
        if st.button(f"🚩 선점하기 (반경 {radius_m}m)", use_container_width=True):
            is_overlap = False
            new_pos = (t['lat'], t['lon'])
            for _, row in df.iterrows():
                if row['lat'] != 0:
                    if str(row['owner']).split('|')[0].strip() == selected_owner: continue
                    dist = geodesic(new_pos, (row['lat'], row['lon'])).meters
                    existing_radius = 1000 if "[동네]" in str(row['owner']) else 100
                    if dist < (radius_m + existing_radius) / 2:
                        is_overlap = True; break
            if is_overlap: st.error("중첩되는 구역이 있습니다.")
            else:
                prefix = "[동네] " if t['is_area'] else "[지점] "
                clean_name = t['display_name'].split(']')[-1].strip()
                save_val = f"{selected_owner} | {prefix}{clean_name}"
                payload = {"action": "add", "owner": save_val, "address": t['display_name'], "lat": t['lat'], "lon": t['lon']}
                requests.post(API_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
                st.session_state.temp_loc = None
                st.cache_data.clear(); time.sleep(1); st.rerun()

# --- 메인 지도 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")
m = folium.Map(location=st.session_state.map_center, zoom_start=15)

for _, row in df.iterrows():
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
