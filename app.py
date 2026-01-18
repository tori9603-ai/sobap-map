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
st.set_page_config(page_title="소중한밥상 마스터 관리자", layout="wide")

# ⚠️ 사장님이 새로 배포하신 구글 앱 스크립트 URL입니다.
API_URL = "https://script.google.com/macros/s/AKfycbxDw8kU3K2LzcaM0zOStvwBdsZs98zyjNzQtgxJlRnZcjTCA70RUEQMLmg4lHTCb9uQ/exec"

def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            # 시트 헤더 순서 준수: [A] owner, [B] address, [C] lat, [D] lon
            df = pd.DataFrame(data[1:], columns=data[0])
            df['owner'] = df['owner'].astype(str).str.strip()
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            # 무의미한 데이터 필터링
            df = df[~df['owner'].isin(['0', '', 'nan'])]
            return df
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
    except:
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

df = get_data()

# 세션 상태 관리 (수정 모드 등)
if 'map_center' not in st.session_state: st.session_state.map_center = [37.5665, 126.9780]
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = 11
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False

# =========================================================
# 🍱 사이드바: 통합 관리 시스템
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # --- 1️⃣ 점주 관리 (선택/수정/삭제) ---
    st.header("1️⃣ 점주 관리")
    
    raw_owners = df['owner'].unique().tolist()
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in raw_owners if name.strip()])))
    
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)

    # 💡 [신규] 점주 수정 및 삭제 버튼
    if selected_owner != "선택":
        col_edit, col_del = st.columns(2)
        with col_edit:
            if st.button("✏️ 이름 수정"):
                st.session_state.edit_mode = True
        with col_del:
            if st.button("🗑️ 점주 삭제"):
                # 해당 점주가 포함된 모든 행 삭제 (동기화)
                new_df = df[~df['owner'].str.contains(selected_owner, na=False)]
                sync_payload = [new_df.columns.tolist()] + new_df.values.tolist()
                requests.post(API_URL, data=json.dumps({"action": "sync", "data": sync_payload}))
                st.success(f"'{selected_owner}' 점주 및 관련 데이터 삭제 완료!")
                time.sleep(1)
                st.rerun()

        # 이름 수정 입력창 (수정 버튼 클릭 시 나타남)
        if st.session_state.edit_mode:
            new_name = st.text_input("새로운 점주 이름을 입력하세요", value=selected_owner)
            if st.button("✅ 수정 확정"):
                # 기존 데이터에서 점주 이름 부분만 일괄 변경
                df['owner'] = df['owner'].apply(lambda x: x.replace(selected_owner, new_name) if selected_owner in x else x)
                sync_payload = [df.columns.tolist()] + df.values.tolist()
                requests.post(API_URL, data=json.dumps({"action": "sync", "data": sync_payload}))
                st.session_state.edit_mode = False
                st.success(f"이름이 '{new_name}'(으)로 변경되었습니다.")
                time.sleep(1)
                st.rerun()

    # 점주 신규 등록 기능
    with st.expander("➕ 신규 점주 등록"):
        add_name = st.text_input("새 점주 성함")
        if st.button("시트에 영구 등록"):
            if add_name:
                payload = {"action": "add", "owner": add_name, "address": "신규등록", "lat": 0, "lon": 0}
                requests.post(API_URL, data=json.dumps(payload))
                st.success(f"'{add_name}' 점주님 등록 완료!")
                st.rerun()

    st.markdown("---")

    if selected_owner != "선택":
        # 📍 선점 내역 관리 (삭제 버튼 포함)
        st.header("📍 선점 내역")
        owner_data = df[(df['owner'].str.contains(selected_owner, na=False)) & (df['lat'] != 0)]
        if not owner_data.empty:
            for idx, row in owner_data.iterrows():
                place_name = str(row['owner']).split('|')[-1].strip() if '|' in str(row['owner']) else "상세 위치"
                c1, c2 = st.columns([4, 1])
                with c1:
                    if st.button(f"🏠 {place_name}", key=f"mv_{idx}"):
                        st.session_state.map_center = [row['lat'], row['lon']]
                        st.session_state.map_zoom = 17
                        st.rerun()
                with c2:
                    if st.button("❌", key=f"rm_{idx}"):
                        new_df = df.drop(idx)
                        requests.post(API_URL, data=json.dumps({"action": "sync", "data": [new_df.columns.tolist()] + new_df.values.tolist()}))
                        st.rerun()
        else: st.write("선점된 구역 없음")

        st.markdown("---")

        # 2️⃣ 새 장소 검색 및 선점 (연결 지연 방지 로직 포함)
        st.header("2️⃣ 새 장소 선점")
        search_addr = st.text_input("아파트/동네 검색")
        
        col_sch, col_clr = st.columns(2)
        with col_sch:
            if st.button("🔍 검색"):
                try:
                    random_agent = f"sobap_manager_{int(time.time())}"
                    geolocator = Nominatim(user_agent=random_agent)
                    res = geolocator.geocode(search_addr, exactly_one=False, timeout=15)
                    if res: st.session_state.search_results = res
                    else: st.warning("결과 없음")
                except: st.error("연결 지연: 잠시 후 다시 시도하세요.")
        with col_clr:
            if st.button("♻️ 초기화"):
                st.session_state.search_results = []
                st.session_state.temp_loc = None
                st.rerun()

        if st.session_state.search_results:
            res_map = {r.address: r for r in st.session_state.search_results}
            sel_res = st.selectbox("정확한 주소 선택", list(res_map.keys()))
            if st.button("📍 위치 확인"):
                t = res_map[sel_res]
                st.session_state.temp_loc = {"lat": t.latitude, "lon": t.longitude, "name": sel_res.split(',')[0].strip(), "full_addr": sel_res}
                st.session_state.map_center = [t.latitude, t.longitude]
                st.session_state.map_zoom = 17
                st.rerun()

        if st.session_state.temp_loc:
            t = st.session_state.temp_loc
            if st.button(f"🚩 '{t['name']}' 선점!", use_container_width=True):
                save_val = f"{selected_owner} | {t['name']}"
                payload = {"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}
                requests.post(API_URL, data=json.dumps(payload))
                st.session_state.temp_loc = None
                st.success("선점 완료!")
                st.rerun()

# =========================================================
# 🗺️ 메인 화면: 지도
# =========================================================
st.title("🗺️ 소중한밥상 실시간 관제 센터")

m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

for _, row in df.iterrows():
    if row['lat'] != 0:
        try:
            owner_only = str(row['owner']).split('|')[0].strip()
            color = "red" if owner_only == selected_owner else "blue"
            folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
            folium.Circle(location=[row['lat'], row['lon']], radius=100, color=color, fill=True, fill_opacity=0.15).add_to(m)
        except: continue

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
