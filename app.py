import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 통합 관리 센터", layout="wide")

# ⚠️ 사장님의 구글 앱 스크립트 URL과 제공해주신 카카오 API 키입니다.
API_URL = "https://script.google.com/macros/s/AKfycbxDw8kU3K2LzcaM0zOStvwBdsZs98zyjNzQtgxJlRnZcjTCA70RUEQMLmg4lHTCb9uQ/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79"

def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            # 시트 헤더: owner, address, lat, lon
            df = pd.DataFrame(data[1:], columns=data[0])
            df['owner'] = df['owner'].astype(str).str.strip()
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            df = df[~df['owner'].isin(['0', '', 'nan'])]
            return df
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
    except:
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

# 💡 카카오 API를 이용한 정밀 주소 검색 함수
def get_kakao_location(query):
    url = f"https://dapi.kakao.com/v2/local/search/address.json?query={query}"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.json().get('documents', [])
        return []
    except:
        return []

df = get_data()

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []

with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # 1️⃣ 점주 선택
    st.header("1️⃣ 점주 선택")
    raw_owners = df['owner'].unique().tolist()
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in raw_owners if name.strip()])))
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    if selected_owner != "선택":
        # 📍 현재 선점 목록
        st.header("📍 선점 내역")
        owner_data = df[(df['owner'].str.contains(selected_owner, na=False)) & (df['lat'] != 0)]
        if not owner_data.empty:
            for idx, row in owner_data.iterrows():
                place_name = str(row['owner']).split('|')[-1].strip()
                c1, c2 = st.columns([4, 1])
                with c1:
                    if st.button(f"🏠 {place_name}", key=f"mv_{idx}"):
                        st.session_state.map_center = [row['lat'], row['lon']]
                        st.rerun()
                with c2:
                    if st.button("❌", key=f"rm_{idx}"):
                        new_df = df.drop(idx)
                        requests.post(API_URL, data=json.dumps({"action": "sync", "data": [new_df.columns.tolist()] + new_df.values.tolist()}))
                        st.rerun()

        st.markdown("---")

        # 2️⃣ 카카오 정밀 검색
        st.header("2️⃣ 새 장소 정밀 검색")
        search_addr = st.text_input("상세 주소 또는 건물명 입력")
        if st.button("🔍 카카오 주소 찾기"):
            results = get_kakao_location(search_addr)
            if results:
                st.session_state.search_results = results
                st.success(f"{len(results)}개의 정확한 위치를 찾았습니다.")
            else:
                st.warning("검색 결과가 없습니다. 상세 주소를 입력해 보세요.")

        if st.session_state.search_results:
            res_options = {r['address_name']: r for r in st.session_state.search_results}
            sel_res_addr = st.selectbox("정확한 주소를 선택하세요", list(res_options.keys()))
            
            if st.button("📍 지도에서 위치 확인"):
                target = res_options[sel_res_addr]
                lat, lon = float(target['y']), float(target['x'])
                # 행정구역(동네) 여부 판별
                is_area = target['address_type'] == 'REGION'
                
                st.session_state.temp_loc = {
                    "lat": lat, "lon": lon, 
                    "name": sel_res_addr.split(' ')[-1], 
                    "full_addr": sel_res_addr,
                    "is_area": is_area
                }
                st.session_state.map_center = [lat, lon]
                st.rerun()

        # 3️⃣ 최종 선점
        if st.session_state.temp_loc:
            t = st.session_state.temp_loc
            tag = "[동네] " if t['is_area'] else ""
            if st.button(f"🚩 {tag}'{t['name']}' 최종 선점!"):
                save_val = f"{selected_owner} | {tag}{t['name']}"
                payload = {"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}
                requests.post(API_URL, data=json.dumps(payload))
                st.session_state.temp_loc = None
                st.success("영업권 선점 완료!")
                st.rerun()

# --- 메인 화면: 지도 표시 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")
m = folium.Map(location=st.session_state.map_center, zoom_start=17)

for _, row in df.iterrows():
    if row['lat'] != 0:
        owner_name = str(row['owner']).split('|')[0].strip()
        color = "red" if owner_name == selected_owner else "blue"
        radius_val = 1000 if "[동네]" in str(row['owner']) else 100
        folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
        folium.Circle(location=[row['lat'], row['lon']], radius=radius_val, color=color, fill=True, fill_opacity=0.15).add_to(m)

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=1000 if t['is_area'] else 100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
