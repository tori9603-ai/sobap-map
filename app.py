import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 마스터 관리자", layout="wide")

# ⚠️ 사장님의 정보
API_URL = "https://script.google.com/macros/s/AKfycbxDw8kU3K2LzcaM0zOStvwBdsZs98zyjNzQtgxJlRnZcjTCA70RUEQMLmg4lHTCb9uQ/exec"
KAKAO_API_KEY = "57f491c105b67119ba2b79ec33cfff79"

def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            # 데이터 방어: 모든 값을 글자로 강제 변환
            df['owner'] = df['owner'].astype(str).str.strip()
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce').fillna(0)
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce').fillna(0)
            df = df[~df['owner'].isin(['0', '', 'nan'])]
            return df
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])
    except:
        return pd.DataFrame(columns=['owner', 'address', 'lat', 'lon'])

# 💡 [진단 기능 강화] 카카오 API 상세 에러 출력
def get_kakao_location(query):
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    url = f"https://dapi.kakao.com/v2/local/search/address.json?query={query}"
    
    try:
        res = requests.get(url, headers=headers)
        
        # 403 에러 발생 시 카카오가 보낸 진짜 이유를 확인합니다.
        if res.status_code == 403:
            err_msg = res.json().get('message', '알 수 없는 이유로 차단됨')
            return [], f"❌ 카카오 서버 거부 (403): {err_msg}"
        elif res.status_code == 401:
            return [], "❌ API 키 인증 실패: REST API 키가 맞는지 확인하세요."
        elif res.status_code != 200:
            return [], f"❌ 기타 오류: {res.status_code}"
            
        data = res.json()
        if data.get('documents'):
            return data['documents'], "✅ 성공"
        
        # 주소 검색 결과 없으면 키워드로 재검색
        kw_url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}"
        res_kw = requests.get(kw_url, headers=headers).json()
        if res_kw.get('documents'):
            return res_kw['documents'], "✅ 키워드 검색 성공"
            
        return [], "❓ 검색 결과가 없습니다."
    except Exception as e:
        return [], f"❌ 연결 오류: {str(e)}"

df = get_data()

# 세션 상태 관리
if 'map_center' not in st.session_state: st.session_state.map_center = [35.1796, 129.0756]
if 'temp_loc' not in st.session_state: st.session_state.temp_loc = None
if 'search_results' not in st.session_state: st.session_state.search_results = []

# --- 사이드바 ---
with st.sidebar:
    st.title("🍱 소중한밥상 관리")
    
    st.header("1️⃣ 점주 관리")
    with st.expander("➕ 신규 점주 등록"):
        add_name = st.text_input("새 점주 성함")
        if st.button("구글 시트에 영구 등록"):
            if add_name:
                requests.post(API_URL, data=json.dumps({"action": "add", "owner": add_name, "address": "신규등록", "lat": 0, "lon": 0}))
                st.success(f"'{add_name}' 등록 완료!")
                st.rerun()

    unique_owners = sorted(list(set([name.split('|')[0].strip() for name in df['owner'] if name.strip()])))
    selected_owner = st.selectbox("관리할 점주 선택", ["선택"] + unique_owners)
    
    st.markdown("---")

    if selected_owner != "선택":
        st.header("2️⃣ 새 장소 검색")
        search_addr = st.text_input("주소 또는 건물명 입력")
        if st.button("🔍 카카오 정밀 검색"):
            results, status = get_kakao_location(search_addr)
            if results:
                st.session_state.search_results = results
                st.success(status)
            else:
                st.error(status) # 에러 이유를 빨간색으로 표시

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
            if st.button(f"🚩 '{t['name']}' 최종 선점!"):
                save_val = f"{selected_owner} | {t['name']}"
                payload = {"action": "add", "owner": save_val, "address": t['full_addr'], "lat": t['lat'], "lon": t['lon']}
                requests.post(API_URL, data=json.dumps(payload))
                st.session_state.temp_loc = None
                st.success("선점 완료!")
                st.rerun()

# --- 메인 화면 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")
m = folium.Map(location=st.session_state.map_center, zoom_start=17)

for _, row in df.iterrows():
    if row['lat'] != 0:
        try:
            owner_label = str(row['owner']).split('|')[0].strip()
            color = "red" if owner_label == selected_owner else "blue"
            folium.Marker([row['lat'], row['lon']], popup=str(row['owner']), icon=folium.Icon(color=color)).add_to(m)
            folium.Circle(location=[row['lat'], row['lon']], radius=100, color=color, fill=True, fill_opacity=0.15).add_to(m)
        except: continue

if st.session_state.temp_loc:
    t = st.session_state.temp_loc
    folium.Marker([t['lat'], t['lon']], icon=folium.Icon(color="green", icon="star")).add_to(m)
    folium.Circle(location=[t['lat'], t['lon']], radius=100, color="green", dash_array='5, 5').add_to(m)

st_folium(m, width="100%", height=800, key=f"map_display")
