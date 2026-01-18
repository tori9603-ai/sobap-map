import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 관제 시스템", layout="wide")

# ⚠️ 사장님의 고유 정보 (순서: owner, address, lat, lon)
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

# 💡 [자가 진단] 카카오 API 응답 상태를 체크하는 강화된 검색 함수
def get_kakao_location(query):
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    
    # 1차 주소 검색
    addr_url = f"https://dapi.kakao.com/v2/local/search/address.json?query={query}"
    res = requests.get(addr_url, headers=headers)
    
    if res.status_code == 401:
        return [], "❌ API 키 인증 실패 (키를 다시 확인하거나 플랫폼 설정을 확인하세요)"
    elif res.status_code != 200:
        return [], f"❌ 카카오 서버 오류 (코드: {res.status_code})"
    
    data = res.json()
    if data.get('documents'):
        return data['documents'], "✅ 성공"
    
    # 2차 키워드(건물명) 검색
    kw_url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}"
    res_kw = requests.get(kw_url, headers=headers).json()
    if res_kw.get('documents'):
        return res_kw['documents'], "✅ 성공 (키워드로 찾음)"
    
    return [], "❓ 검색 결과가 없습니다. 주소를 더 짧게 입력해 보세요 (예: 동패동 2076)"

df = get_data()

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []

with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    # 1️⃣ 점주 관리
    st.header("1️⃣ 점주 관리")
    with st.expander("➕ 신규 점주 등록"):
        add_name = st.text_input("새 점주 이름")
        if st.button("시트에 등록"):
            if add_name:
                # [A]owner, [B]address, [C]lat, [D]lon 순서 준수
                requests.post(API_URL, data=json.dumps({"action": "add", "owner": add_name, "address": "신규등록", "lat": 0, "lon": 0}))
                st.success(f"'{add_name}' 등록 완료!")
                st.rerun()

    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in df['owner'] if name.strip()])))
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    st.markdown("---")

    if selected_owner != "선택":
        # 📍 선점 내역 리스트
        st.header("📍 현재 선점 내역")
        owner_data = df[df['owner'].str.contains(selected_owner, na=False)]
        for idx, row in owner_data.iterrows():
            if row['lat'] != 0:
                place_display = str(row['owner']).split('|')[-1].strip()
                c1, c2 = st.columns([4, 1])
                with c1:
                    if st.button(f"🏠 {place_display}", key=f"mv_{idx}"):
                        st.session_state.map_center = [row['lat'], row['lon']]
                        st.rerun()
                with c2:
                    if st.button("❌", key=f"del_{idx}"):
                        new_df = df.drop(idx)
                        sync_data = [new_df.columns.tolist()] + new_df.values.tolist()
                        requests.post(API_URL, data=json.dumps({"action": "sync", "data": sync_data}))
                        st.rerun()

        st.markdown("---")

        # 2️⃣ 정밀 검색 (자가 진단 메시지 포함)
        st.header("2️⃣ 새 장소 검색")
        search_addr = st.text_input("주소 또는 건물명 입력")
        
        if st.button("🔍 카카오 정밀 검색"):
            results, status = get_kakao_location(search_addr)
            if results:
                st.session_state.search_results = results
                st.success(status)
            else:
                st.error(status) # 무엇이 문제인지 빨간색으로 표시

        if st.session_state.search_results:
            res_options = { (r.get('address_name') or r.get('place_name')): r for r in st.session_state.search_results }
            sel_res_addr = st.selectbox("정확한 장소 선택", list(res_options.keys()))
            if st.button("📍 지도 위치 확인"):
                target = res_options[sel_res_addr]
                lat, lon = float(target['y']), float(target['x'])
                st.session_state.temp_loc = {"lat": lat, "lon": lon, "name": sel_res_addr.split(' ')[-1], "full_addr": sel_res_addr}
                st.session_state.map_center = [lat, lon]
                st.rerun()

        if st.session_state.temp_loc:
            t = st.session_state.temp_loc
            if st.button(f"🚩 '{t['name']}' 선점!", use_container_width=True):
                save_val = f"{selected_owner} | {t['name']}"
                # 구글 시트 데이터 정렬 순서 준수 (image_45d428.png 기반)
                payload = {"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}
                requests.post(API_URL, data=json.dumps(payload))
                st.session_state.temp_loc = None
                st.success("선점 완료!")
                st.rerun()

# --- 메인 지도 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")
m = folium.Map(location=st.session_state.map_center, zoom_start=17)

for _, row in df.iterrows():
    if row['lat'] != 0:
        try:
            owner_label = str(row['owner']).split('|')[0].strip()
            color = "red" if owner_label == selected_owner else "blue"
            radius = 1000 if "[동네]" in str(row['owner']) else 100
            folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
            folium.Circle(location=[row['lat'], row['lon']], radius=radius, color=color, fill=True, fill_opacity=0.15).add_to(m)
        except: continue

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_{st.session_state.map_center}")
