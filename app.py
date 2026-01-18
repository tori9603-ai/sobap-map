import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 마스터 관리자", layout="wide")

# 2. 사장님이 복사하신 웹 앱 URL (입력 완료)
API_URL = "https://script.google.com/macros/s/AKfycbxmLywtQIA-6Ay5_KczYt3zNIoGekzkdWD4I3X80PORIMw8gUNHMsZTvip8LXdopxTJ/exec"

# --- 데이터 로드 함수 ---
def get_data():
    try:
        # 로그인 창을 건너뛰고 데이터를 가져오기 위해 리다이렉션을 허용합니다.
        response = requests.get(API_URL, follow_redirects=True)
        data = response.json()
        # 데이터가 있으면 첫 줄을 제목으로 프레임을 만듭니다.
        if len(data) > 0:
            df = pd.DataFrame(data[1:], columns=data[0])
            return df
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])
    except Exception as e:
        st.error(f"데이터 연결 중... 구글 시트 첫 줄에 lat, lon, owner가 있는지 확인하세요. (에러: {e})")
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])

# --- 사이드바 메뉴 ---
st.sidebar.title("🍱 관리자 메뉴")
menu = st.sidebar.radio("기능 선택", ["🗺️ 지도 보기 및 검색", "👥 지점 추가", "📊 데이터 관리(수정/삭제)"])

df = get_data()

# --- [1] 지도 보기 및 검색 ---
if menu == "🗺️ 지도 보기 및 검색":
    st.title("🗺️ 소중한밥상 '대동여지도'")
    
    search_q = st.sidebar.text_input("📍 지점명 검색")
    if search_q and not df.empty:
        df = df[df['owner'].astype(str).str.contains(search_q, na=False)]

    # 기본 지도 (서울 중심)
    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
    
    if not df.empty:
        for _, row in df.iterrows():
            try:
                folium.Marker(
                    location=[float(row['lat']), float(row['lon'])],
                    popup=str(row['owner']),
                    tooltip=str(row['owner'])
                ).add_to(m)
            except: pass
            
    st_folium(m, width="100%", height=600)
    st.success("✅ 구글 시트와 실시간 연동 중입니다.")

# --- [2] 지점 추가 ---
elif menu == "👥 지점 추가":
    st.title("👥 신규 지점 등록")
    with st.form("add_form"):
        new_owner = st.text_input("지점/점주 이름")
        new_addr = st.text_input("지점 주소 (예: 부산시 해운대구 ...)")
        submitted = st.form_submit_button("등록하기")
        
        if submitted:
            geolocator = Nominatim(user_agent="sobap_bot")
            location = geolocator.geocode(new_addr)
            if location:
                payload = {"action": "add", "lat": location.latitude, "lon": location.longitude, "owner": new_owner}
                requests.post(API_URL, data=json.dumps(payload))
                st.success(f"✅ {new_owner} 지점이 등록되었습니다!")
                st.balloons()
            else:
                st.error("주소를 찾을 수 없습니다. 정확한 주소를 입력해주세요.")

# --- [3] 데이터 관리 ---
elif menu == "📊 데이터 관리(수정/삭제)":
    st.title("📊 전체 데이터 관리")
    if not df.empty:
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        if st.button("변경사항 시트에 저장하기"):
            full_data = [edited_df.columns.tolist()] + edited_df.values.tolist()
            payload = {"action": "sync", "data": full_data}
            requests.post(API_URL, data=json.dumps(payload))
            st.success("✅ 구글 시트 업데이트 완료!")
    else:
        st.warning("데이터가 없습니다. 지점을 먼저 추가해주세요.")
