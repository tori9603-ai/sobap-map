import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.geocoders import Nominatim

# 1. 페이지 및 기본 설정
st.set_page_config(page_title="소중한밥상 통합 관제 시스템", layout="wide")

# ⚠️ 사장님의 고유 정보 (절대 수정 금지)
API_URL = "https://script.google.com/macros/s/AKfycbxDw8kU3K2LzcaM0zOStvwBdsZs98zyjNzQtgxJlRnZcjTCA70RUEQMLmg4lHTCb9uQ/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79"

# 2. 데이터 불러오기 및 정제 (AttributeError 완벽 방지)
def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            # 시트 구조: owner, address, lat, lon
            df = pd.DataFrame(data[1:], columns=data[0])
            # 모든 데이터를 강제로 글자로 변환하여 숫자 0 등으로 인한 오류 차단
            df['owner'] = df['owner'].astype(str).str.strip()
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            # 유효하지 않은 데이터 제외
            df = df[~df['owner'].isin(['0', '', 'nan'])]
            return df
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
    except:
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

# 3. 하이브리드 검색 엔진 (카카오 대기 중에도 작동)
def get_location_smart(query):
    # 1단계: 카카오 API 시도 (승인 완료 시 자동 작동)
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    try:
        # 주소 검색 시도
        res = requests.get(f"https://dapi.kakao.com/v2/local/search/address.json?query={query}", headers=headers, timeout=5)
        if res.status_code == 200 and res.json().get('documents'):
            return res.json()['documents'], "✅ 카카오 정밀 검색 성공"
        
        # 키워드(건물명) 검색 시도
        res_kw = requests.get(f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}", headers=headers, timeout=5)
        if res_kw.status_code == 200 and res_kw.json().get('documents'):
            return res_kw.json()['documents'], "✅ 카카오 키워드 검색 성공"
    except: pass

    # 2단계: 카카오 실패 시(승인 대기 중) 비상용 Nominatim 실행
    try:
        geolocator = Nominatim(user_agent=f"sobap_final_{int(time.time())}")
        # 한국 주소로 범위를 한정하여 검색
        res = geolocator.geocode(f"{query}, 대한민국", exactly_one=False, timeout=10)
        if res:
            results = []
            for r in res:
                # 카카오 데이터 형식과 동일하게 변환
                results.append({
                    "address_name": r.address,
                    "y": r.latitude,
                    "x": r.longitude,
                    "place_name": r.address.split(',')[0]
                })
            return results, "⚠️ 카카오 승인 대기 중 (비상용 엔진 사용)"
    except: pass

    return [], "❓ 위치를 찾을 수 없습니다. 주소를 더 정확히 입력해 주세요."

df = get_data()

# 세션 상태 관리 (새로고침 시 데이터 유지)
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []

# =========================================================
# 🍱 왼쪽 사이드바: 관리 시스템
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # 1️⃣ 점주 관리 (등록 및 선택)
    st.header("1️⃣ 점주 관리")
    with st.expander("➕ 신규 점주 등록"):
        add_name = st.text_input("새로운 점주 성함 입력")
        if st.button("구글 시트에 영구 등록"):
            if add_name:
                payload = {"action": "add", "owner": add_name, "address": "신규등록", "lat": 0, "lon": 0}
                requests.post(API_URL, data=json.dumps(payload))
                st.success(f"'{add_name}' 등록 완료! 새로고침 하세요.")
                st.rerun()

    # 점주 목록 (시트 A열 데이터 기준)
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in df['owner'] if name.strip()])))
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    st.markdown("---")

    if selected_owner != "선택":
        # 📍 현재 선점 내역 (삭제 및 이동 기능)
        st.header("📍 현재 선점 내역")
        owner_data = df[(df['owner'].str.contains(selected_owner, na=False)) & (df['lat'] != 0)]
        if not owner_data.empty:
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
                        st.rerun()
        else: st.write("선점된 구역 없음")

        st.markdown("---")

        # 2️⃣ 정밀 검색 및 선점 (카카오 + 비상용)
        st.header("2️⃣ 새 장소 선점")
        search_addr = st.text_input("주소 또는 아파트명 입력", placeholder="예: 이진베이시티, 동패동 2076")
        
        if st.button("🔍 위치 찾기"):
            results, status = get_location_smart(search_addr)
            if results:
                st.session_state.search_results = results
                st.info(status)
            else:
                st.warning(status)

        if st.session_state.search_results:
            res_options = { (r.get('address_name') or r.get('place_name')): r for r in st.session_state.search_results }
            sel_res_addr = st.selectbox("정확한 위치를 선택하세요", list(res_options.keys()))
            
            if st.button("📍 지도에서 위치 확인"):
                target = res_options[sel_res_addr]
                lat, lon = float(target['y']), float(target['x'])
                st.session_state.temp_loc = {
                    "lat": lat, "lon": lon, 
                    "name": sel_res_addr.split(' ')[-1] if ',' not in sel_res_addr else sel_res_addr.split(',')[-2].strip(),
                    "full_addr": sel_res_addr
                }
                st.session_state.map_center = [lat, lon]
                st.rerun()

        # 3️⃣ 최종 선점 (요청하신 대로 버튼 이름 고정)
        if st.session_state.temp_loc:
            st.markdown("---")
            t = st.session_state.temp_loc
            if st.button("🚩 해당 주소 선점하기", use_container_width=True):
                save_val = f"{selected_owner} | {t['name']}"
                # 시트 순서: owner, address, lat, lon
                payload = {"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}
                requests.post(API_URL, data=json.dumps(payload))
                st.session_state.temp_loc = None
                st.session_state.search_results = []
                st.success("영업권 선점이 완료되었습니다!")
                st.rerun()

# =========================================================
# 🗺️ 메인 화면: 실시간 관제 시스템
# =========================================================
st.title("🗺️ 소중한밥상 실시간 관제 시스템")

m = folium.Map(location=st.session_state.map_center, zoom_start=17)

# 등록된 데이터 지도에 표시
for _, row in df.iterrows():
    if row['lat'] != 0:
        try:
            full_owner_info = str(row['owner'])
            owner_only = full_owner_info.split('|')[0].strip()
            # 선택된 점주의 데이터는 빨간색, 나머지는 파란색
            color = "red" if owner_only == selected_owner else "blue"
            
            folium.Marker([row['lat'], row['lon']], popup=full_owner_info, icon=folium.Icon(color=color)).add_to(m)
            folium.Circle(location=[row['lat'], row['lon']], radius=100, color=color, fill=True, fill_opacity=0.15).add_to(m)
        except: continue

# 작업 중인 임시 위치 표시 (초록색 별)
if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_display_{st.session_state.map_center}")
