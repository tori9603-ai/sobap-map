import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 마스터 관리자", layout="wide")

# 2. 구글 앱 스크립트 URL
API_URL = "https://script.google.com/macros/s/AKfycbxmLywtQIA-6Ay5_KczYt3zNIoGekzkdWD4I3X80PORIMw8gUNHMsZTvip8LXdopxTJ/exec"

def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
            df = df.dropna(subset=['lat', 'lon'])
            return df
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])
    except:
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])

df = get_data()

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [37.5665, 126.9780]
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = 11
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []

# =========================================================
# 🍱 왼쪽 사이드바: 점주 및 장소 통합 관리
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 마스터")
    
    # --- 1️⃣ 점주 관리 (추가/수정/삭제) ---
    st.header("1️⃣ 점주 관리")
    
    # 현재 등록된 점주 리스트 추출
    raw_owners = df['owner'].astype(str).tolist()
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in raw_owners])))
    
    # 점주 선택 드롭다운
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    # [수정 및 삭제 버튼] - 점주가 선택되었을 때만 표시
    if selected_owner != "선택":
        col_edit, col_del = st.columns(2)
        with col_edit:
            if st.button("✏️ 이름 수정"):
                st.session_state.edit_mode = True
        with col_del:
            if st.button("🗑️ 점주 삭제"):
                # 해당 점주의 모든 데이터 삭제
                new_df = df[~df['owner'].str.contains(selected_owner)]
                requests.post(API_URL, data=json.dumps({"action": "sync", "data": [new_df.columns.tolist()] + new_df.values.tolist()}))
                st.success(f"{selected_owner} 점주 정보 삭제 완료")
                st.rerun()

        # 이름 수정 모드 활성화 시
        if st.session_state.get('edit_mode', False):
            new_name = st.text_input("새로운 점주 이름 입력", value=selected_owner)
            if st.button("✅ 수정 완료"):
                # 모든 관련 행의 이름 변경
                df['owner'] = df['owner'].apply(lambda x: x.replace(selected_owner, new_name) if selected_owner in x else x)
                requests.post(API_URL, data=json.dumps({"action": "sync", "data": [df.columns.tolist()] + df.values.tolist()}))
                st.session_state.edit_mode = False
                st.success("이름이 변경되었습니다.")
                st.rerun()

    # [신규 점주 추가]
    with st.expander("➕ 신규 점주 등록"):
        add_name = st.text_input("신규 점주 성함")
        if st.button("신규 등록"):
            if add_name and add_name not in unique_owners:
                st.success(f"'{add_name}' 점주님이 등록되었습니다. 이제 장소를 검색해 선점하세요!")
                # 메모리에 임시 추가 (첫 선점 시 시트에 기록됨)
                unique_owners.append(add_name)
                st.rerun()
            else:
                st.error("이름을 입력하거나 중복을 확인하세요.")

    st.markdown("---")

    # --- 2️⃣ 현재 선점 목록 (장소명만 표시) ---
    if selected_owner != "선택":
        st.header("📍 선점 내역")
        owner_data = df[df['owner'].str.contains(selected_owner, na=False)]
        
        if not owner_data.empty:
            for idx, row in owner_data.iterrows():
                place_name = str(row['owner']).split('|')[-1].strip() if '|' in str(row['owner']) else str(row['owner'])
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
            st.write("선점 내역 없음")

        st.markdown("---")

        # --- 3️⃣ 새 장소 검색 및 선점 ---
        st.header("2️⃣ 새 장소 선점")
        search_addr = st.text_input("아파트/동네 검색")
        
        if st.button("🔍 검색"):
            try:
                geolocator = Nominatim(user_agent="sobap_master_v7")
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
                requests.post(API_URL, data=json.dumps({"action": "add", "lat": t['lat'], "lon": t['lon'], "owner": save_val}))
                st.session_state.temp_loc = None
                st.rerun()

# =========================================================
# 🗺️ 메인 화면: 지도
# =========================================================
st.title("🗺️ 소중한밥상 실시간 관제 센터")

m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

for _, row in df.iterrows():
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
