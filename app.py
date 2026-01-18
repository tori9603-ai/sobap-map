import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 마스터", layout="wide")

# 2. 구글 앱 스크립트 URL
API_URL = "https://script.google.com/macros/s/AKfycbxmLywtQIA-6Ay5_KczYt3zNIoGekzkdWD4I3X80PORIMw8gUNHMsZTvip8LXdopxTJ/exec"

def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            # 💡 [핵심 수정] 모든 점주 이름을 강제로 '글자(문자열)'로 변환하여 오류를 방지합니다.
            df['owner'] = df['owner'].astype(str).str.strip()
            # 위경도 숫자 변환 및 비정상 데이터(0 포함) 필터링 준비
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            # 이름이 '0'이거나 비어있는 행은 목록에서 제외
            df = df[~df['owner'].isin(['0', '', 'nan'])]
            return df
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])
    except Exception as e:
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])

df = get_data()

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [37.5665, 126.9780]
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = 11
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []

# =========================================================
# 🍱 왼쪽 사이드바: 관리 프로세스
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 마스터")
    
    st.header("1️⃣ 점주 관리")
    
    # 중복 제거 및 이름 정제
    unique_owners = sorted(df['owner'].apply(lambda x: x.split('|')[0].strip()).unique().tolist())
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    # [신규 점주 추가] 
    with st.expander("➕ 신규 점주 등록"):
        add_name = st.text_input("새로운 점주 성함")
        if st.button("구글 시트에 영구 등록"):
            if add_name and add_name not in unique_owners:
                # 💡 등록 시 문자열임을 명확히 하기 위해 이름 뒤에 공백 하나를 제거하고 전송
                payload = {"action": "add", "lat": 0, "lon": 0, "owner": str(add_name).strip()}
                requests.post(API_URL, data=json.dumps(payload))
                st.success(f"'{add_name}' 점주님 등록 완료! 새로고침 후 선택해 주세요.")
                st.rerun()
            else:
                st.warning("이름을 입력하거나 중복을 확인하세요.")

    if selected_owner != "선택":
        col_edit, col_del = st.columns(2)
        with col_edit:
            if st.button("✏️ 이름 수정"): st.session_state.edit_mode = True
        with col_del:
            if st.button("🗑️ 점주 삭제"):
                new_df = df[~df['owner'].str.contains(selected_owner, na=False)]
                requests.post(API_URL, data=json.dumps({"action": "sync", "data": [new_df.columns.tolist()] + new_df.values.tolist()}))
                st.rerun()

    st.markdown("---")

    # --- 2️⃣ 선점 내역 관리 ---
    if selected_owner != "선택":
        st.header("📍 선점 내역")
        # 해당 점주 데이터 중 실제 좌표가 있는 것만 (lat 0 제외)
        owner_data = df[(df['owner'].str.contains(selected_owner, na=False)) & (df['lat'] != 0)]
        
        if not owner_data.empty:
            for idx, row in owner_data.iterrows():
                place_name = str(row['owner']).split('|')[-1].strip() if '|' in str(row['owner']) else "위치 정보 없음"
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
        else:
            st.write("선점된 장소가 없습니다.")

        st.markdown("---")

        # --- 3️⃣ 새 장소 선점 ---
        st.header("2️⃣ 새 장소 선점")
        search_addr = st.text_input("아파트/동네 검색")
        
        if st.button("🔍 검색"):
            try:
                geolocator = Nominatim(user_agent="sobap_master_final_fix")
                res = geolocator.geocode(search_addr, exactly_one=False, timeout=10)
                if res: st.session_state.search_results = res
                else: st.warning("결과 없음")
            except: st.error("연결 지연")

        if st.session_state.search_results:
            res_map = {r.address: r for r in st.session_state.search_results}
            sel_res = st.selectbox("주소 선택", list(res_map.keys()))
            if st.button("📍 위치 확인"):
                t = res_map[sel_res]
                st.session_state.temp_loc = {"lat": t.latitude, "lon": t.longitude, "name": sel_res.split(',')[0].strip()}
                st.session_state.map_center = [t.latitude, t.longitude]
                st.session_state.map_zoom = 17
                st.rerun()

        if st.session_state.temp_loc:
            t = st.session_state.temp_loc
            if st.button(f"🚩 '{t['name']}' 선점!", use_container_width=True):
                save_val = f"{selected_owner} | {t['name']}"
                payload = {"action": "add", "lat": t['lat'], "lon": t['lon'], "owner": save_val}
                requests.post(API_URL, data=json.dumps(payload))
                st.session_state.temp_loc = None
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
            is_mine = (owner_only == selected_owner)
            color = "red" if is_mine else "blue"
            folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
            folium.Circle(location=[row['lat'], row['lon']], radius=100, color=color, fill=True, fill_opacity=0.15).add_to(m)
        except: continue

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
