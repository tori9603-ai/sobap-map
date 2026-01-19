import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic # 거리 계산을 위한 라이브러리

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 통합 관제 시스템", layout="wide")

# ⚠️ 사장님 정보 (구글 시트 연동)
API_URL = "https://script.google.com/macros/s/AKfycbxDw8kU3K2LzcaM0zOStvwBdsZs98zyjNzQtgxJlRnZcjTCA70RUEQMLmg4lHTCb9uQ/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79"

def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df['owner'] = df['owner'].astype(str).str.strip()
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            df = df[~df['owner'].isin(['0', '', 'nan'])]
            return df
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
    except:
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

def get_location_smart(query):
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    try:
        res = requests.get(f"https://dapi.kakao.com/v2/local/search/address.json?query={query}", headers=headers, timeout=5)
        if res.status_code == 200 and res.json().get('documents'):
            docs = res.json()['documents']
            for d in docs:
                d['is_area'] = d.get('address_type') == 'REGION'
            return docs, "✅ 카카오 검색 성공"
    except: pass

    try:
        geolocator = Nominatim(user_agent=f"sobap_area_collision_{int(time.time())}")
        res = geolocator.geocode(f"{query}, 대한민국", exactly_one=False, timeout=10)
        if res:
            results = []
            for r in res:
                is_area = r.raw.get('class') in ['boundary', 'place'] and r.raw.get('type') in ['administrative', 'suburb', 'city_district']
                results.append({"address_name": r.address, "y": r.latitude, "x": r.longitude, "is_area": is_area})
            return results, "⚠️ 비상용 엔진 사용 중"
    except: pass
    return [], "❓ 검색 결과가 없습니다."

df = get_data()

if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []

with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    st.header("1️⃣ 점주 선택")
    
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in df['owner'] if name.strip()])))
    selected_owner = st.selectbox("점주 선택", ["선택"] + unique_owners)

    if selected_owner != "선택":
        st.markdown("---")
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

        st.markdown("---")
        st.header("2️⃣ 영업권 구역 선점")
        search_addr = st.text_input("동네 이름 또는 아파트명")
        
        if st.button("🔍 위치 찾기"):
            results, status = get_location_smart(search_addr)
            if results:
                st.session_state.search_results = results
                st.info(status)
            else: st.warning(status)

        if st.session_state.search_results:
            res_options = { r['address_name']: r for r in st.session_state.search_results }
            sel_res_addr = st.selectbox("정확한 위치를 선택하세요", list(res_options.keys()))
            if st.button("📍 지도에서 위치 확인"):
                target = res_options[sel_res_addr]
                st.session_state.temp_loc = {
                    "lat": float(target['y']), "lon": float(target['x']),
                    "is_area": target.get('is_area', False),
                    "full_addr": sel_res_addr,
                    "name": sel_res_addr.split(' ')[-1] if not target.get('is_area', False) else sel_res_addr.split(',')[0].strip()
                }
                st.session_state.map_center = [float(target['y']), float(target['x'])]
                st.rerun()

        # 💡 [핵심] 중복 선점 체크 로직
        if st.session_state.temp_loc:
            t = st.session_state.temp_loc
            area_tag = "[동네] " if t.get('is_area', False) else ""
            
            if st.button("🚩 해당 주소 선점하기", use_container_width=True):
                # 1. 겹침 체크 시작
                is_overlap = False
                new_radius = 1000 if t.get('is_area', False) else 100
                new_pos = (t['lat'], t['lon'])

                for _, row in df.iterrows():
                    if row['lat'] != 0:
                        existing_pos = (row['lat'], row['lon'])
                        # 기존 장소의 반경 확인
                        existing_radius = 1000 if "[동네]" in str(row['owner']) else 100
                        # 두 지점 사이의 거리 계산 (미터 단위)
                        dist = geodesic(new_pos, existing_pos).meters
                        
                        # 두 원의 반경 합보다 거리가 짧으면 겹치는 것으로 간주
                        if dist < (new_radius + existing_radius):
                            is_overlap = True
                            overlap_owner = str(row['owner']).split('|')[0].strip()
                            break
                
                if is_overlap:
                    st.error(f"해당 아파트는 다른 점주님이 이미 선점 하였습니다")
                else:
                    # 겹치지 않을 때만 저장 진행
                    save_val = f"{selected_owner} | {area_tag}{t['name']}"
                    payload = {"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}
                    requests.post(API_URL, data=json.dumps(payload))
                    st.session_state.temp_loc = None
                    st.success("선점 완료!")
                    st.rerun()

# --- 메인 화면 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")
m = folium.Map(location=st.session_state.map_center, zoom_start=15)

for _, row in df.iterrows():
    if row['lat'] != 0:
        try:
            full_info = str(row['owner'])
            owner_name = full_info.split('|')[0].strip()
            color = "red" if owner_name == selected_owner else "blue"
            radius_val = 1000 if "[동네]" in full_info else 100
            folium.Marker([row['lat'], row['lon']], popup=full_info, icon=folium.Icon(color=color)).add_to(m)
            folium.Circle(location=[row['lat'], row['lon']], radius=radius_val, color=color, fill=True, fill_opacity=0.15).add_to(m)
        except: continue

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    radius_val = 1000 if t.get('is_area', False) else 100
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=radius_val, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
