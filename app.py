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

# 2. 구글 앱 스크립트 URL (기존 주소 확인)
API_URL = "https://script.google.com/macros/s/AKfycbxmLywtQIA-6Ay5_KczYt3zNIoGekzkdWD4I3X80PORIMw8gUNHMsZTvip8LXdopxTJ/exec"

def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            # 💡 [핵심 수정] 모든 데이터를 강제로 '글자(문자열)'로 변환하여 0 표시 및 오류 방지
            df['owner'] = df['owner'].astype(str).str.strip()
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            # 이름이 '0'이거나 비어있는 무의미한 데이터는 필터링
            df = df[~df['owner'].isin(['0', '', 'nan'])]
            return df
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])
    except:
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])

df = get_data()

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [37.5665, 126.9780]
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = 11
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None

# =========================================================
# 🍱 왼쪽 사이드바: 점주 및 구역 관리
# =========================================================
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    st.header("1️⃣ 점주 관리")
    # 중복 제거 및 이름만 깨끗하게 추출
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in df['owner'] if name.strip()])))
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    # [신규 점주 추가] - 영구 저장 로직 강화
    with st.expander("➕ 신규 점주 등록"):
        add_name = st.text_input("새 점주 성함")
        if st.button("구글 시트에 영구 등록"):
            if add_name and add_name not in unique_owners:
                # 💡 데이터를 보낼 때 명확하게 문자열로 전송
                payload = {"action": "add", "lat": 0, "lon": 0, "owner": str(add_name).strip()}
                requests.post(API_URL, data=json.dumps(payload))
                st.success(f"'{add_name}' 점주님 등록 완료! 리부트 후 선택하세요.")
                st.rerun()
            else:
                st.warning("이름을 입력하거나 중복을 확인하세요.")

    st.markdown("---")

    # --- 2️⃣ 선점 내역 관리 ---
    if selected_owner != "선택":
        st.header("📍 선점 내역")
        # 해당 점주 데이터 중 실제 좌표가 있는 것만 표시
        owner_data = df[(df['owner'].str.contains(selected_owner, na=False)) & (df['lat'] != 0)]
        
        if not owner_data.empty:
            for idx, row in owner_data.iterrows():
                place_name = str(row['owner']).split('|')[-1].strip() if '|' in str(row['owner']) else "상세 위치 없음"
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
            st.write("선점된 구역이 없습니다.")

# =========================================================
# 🗺️ 오른쪽 메인 화면: 지도
# =========================================================
st.title("🗺️ 실시간 영업권 지도")

m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

# 지도에 유효한 좌표만 마커 표시
for _, row in df.iterrows():
    if row['lat'] != 0:
        try:
            owner_only = str(row['owner']).split('|')[0].strip()
            color = "red" if owner_only == selected_owner else "blue"
            folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
            folium.Circle(location=[row['lat'], row['lon']], radius=100, color=color, fill=True, fill_opacity=0.15).add_to(m)
        except: continue

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
