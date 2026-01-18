import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 영업권 관제 센터", layout="wide")

# ⚠️ 사장님의 URL과 키 (그대로 유지)
API_URL = "https://script.google.com/macros/s/AKfycbxDw8kU3K2LzcaM0zOStvwBdsZs98zyjNzQtgxJlRnZcjTCA70RUEQMLmg4lHTCb9uQ/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79"

def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            # 💡 [해결] 모든 데이터를 강제로 글자로 변환하여 AttributeError 방지
            df['owner'] = df['owner'].astype(str).str.strip()
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            # 불필요한 데이터(0, nan) 필터링
            df = df[~df['owner'].isin(['0', '', 'nan'])]
            return df
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
    except:
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

# 💡 [개선] 주소 검색 실패 시 키워드 검색으로 한 번 더 찾는 2중 시스템
def get_kakao_location(query):
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    
    # 1차: 정확한 주소 검색
    addr_url = f"https://dapi.kakao.com/v2/local/search/address.json?query={query}"
    res = requests.get(addr_url, headers=headers).json()
    
    if res.get('documents'):
        return res['documents']
    
    # 2차: 주소로 안 나올 경우 키워드(건물명/지번) 검색 실행
    kw_url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}"
    res_kw = requests.get(kw_url, headers=headers).json()
    return res_kw.get('documents', [])

df = get_data()

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []

with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # 1️⃣ 점주 선택
    st.header("1️⃣ 점주 선택")
    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in df['owner']])))
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    if selected_owner != "선택":
        # 📍 선점 내역 관리
        st.header("📍 현재 선점 목록")
        owner_data = df[df['owner'].str.contains(selected_owner, na=False)]
        for idx, row in owner_data.iterrows():
            if row['lat'] != 0:
                place_name = str(row['owner']).split('|')[-1].strip()
                col_name, col_del = st.columns([3, 1])
                with col_name:
                    if st.button(f"🏠 {place_name}", key=f"mv_{idx}"):
                        st.session_state.map_center = [row['lat'], row['lon']]
                        st.rerun()
                with col_del:
                    if st.button("❌", key=f"del_{idx}"):
                        new_df = df.drop(idx)
                        sync_data = [new_df.columns.tolist()] + new_df.values.tolist()
                        requests.post(API_URL, data=json.dumps({"action": "sync", "data": sync_data}))
                        st.rerun()

        st.markdown("---")

        # 2️⃣ 새 장소 검색 (보강된 로직)
        st.header("2️⃣ 새 장소 정밀 검색")
        search_addr = st.text_input("주소 또는 건물명 입력", placeholder="예: 동패동 2076")
        
        if st.button("🔍 카카오 주소 찾기"):
            results = get_kakao_location(search_addr)
            if results:
                st.session_state.search_results = results
                st.success(f"{len(results)}개의 위치를 찾았습니다.")
            else:
                st.warning("결과가 없습니다. 주소를 더 정확히 입력해 보세요.")

        if st.session_state.search_results:
            # 주소명 또는 장소명 표시
            res_options = {r.get('address_name') or r.get('place_name'): r for r in st.session_state.search_results}
            sel_res_addr = st.selectbox("정확한 주소를 선택하세요", list(res_options.keys()))
            
            if st.button("📍 지도에서 위치 확인"):
                target = res_options[sel_res_addr]
                lat, lon = float(target['y']), float(target['x'])
                
                st.session_state.temp_loc = {
                    "lat": lat, "lon": lon, 
                    "name": sel_res_addr.split(' ')[-1], 
                    "full_addr": sel_res_addr
                }
                st.session_state.map_center = [lat, lon]
                st.rerun()

        # 3️⃣ 최종 선점
        if st.session_state.temp_loc:
            t = st.session_state.temp_loc
            if st.button(f"🚩 '{t['name']}' 최종 선점!", use_container_width=True):
                # 💡 [해결] 시트 순서에 맞춰 정확하게 전송 (owner, address, lat, lon)
                save_val = f"{selected_owner} | {t['name']}"
                payload = {"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}
                requests.post(API_URL, data=json.dumps(payload))
                st.session_state.temp_loc = None
                st.session_state.search_results = []
                st.rerun()

# --- 메인 지도 화면 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")
m = folium.Map(location=st.session_state.map_center, zoom_start=17)

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

st_folium(m, width="100%", height=800, key=f"map_display")
