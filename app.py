import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 마스터 관리자", layout="wide")

# 2. 사장님이 생성하신 웹 앱 URL (입력 완료)
API_URL = "https://script.google.com/macros/s/AKfycbxmLywtQIA-6Ay5_KczYt3zNIoGekzkdWD4I3X80PORIMw8gUNHMsZTvip8LXdopxTJ/exec"

# --- 데이터 로드 함수 ---
def get_data():
    try:
        response = requests.get(API_URL)
        data = response.json()
        # 첫 번째 줄은 제목(lat, lon, owner)이므로 이를 기준으로 데이터프레임을 만듭니다.
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    except Exception as e:
        st.error(f"데이터를 가져오지 못했습니다. 에러: {e}")
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])

# --- 사이드바 메뉴 ---
st.sidebar.title("🍱 관리자 메뉴")
menu = st.sidebar.radio("기능 선택", ["🗺️ 지도 보기 및 검색", "👥 지점 추가", "📊 데이터 관리(수정/삭제)"])

# --- [1] 지도 보기 및 검색 ---
if menu == "🗺️ 지도 보기 및 검색":
    st.title("🗺️ 소중한밥상 '대동여지도'")
    df = get_data()
    
    # 검색 기능
    search_q = st.sidebar.text_input("📍 지점명 또는 점주 검색")
    if search_q:
        df = df[df['owner'].astype(str).str.contains(search_q, na=False)]
        st.sidebar.write(f"검색 결과: {len(df)}건")

    # 지도 생성 (서울 중심)
    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
    
    for _, row in df.iterrows():
        try:
            folium.Marker(
                location=[float(row['lat']), float(row['lon'])],
                popup=str(row['owner']),
                tooltip=str(row['owner'])
            ).add_to(m)
        except:
            pass
            
    st_folium(m, width="100%", height=600)
    st.success("✅ 구글 시트와 실시간 연동 중입니다.")

# --- [2] 지점 추가 ---
elif menu == "👥 지점 추가":
    st.title("👥 신규 지점 등록")
    st.info("주소를 입력하면 지도 좌표를 자동으로 계산하여 시트에 저장합니다.")
    
    with st.form("add_form"):
        new_owner = st.text_input("지점/점주 이름")
        new_addr = st.text_input("지점 주소 (예: 서울시 중구 세종대로 110)")
        submitted = st.form_submit_button("등록하기")
        
        if submitted:
            if new_owner and new_addr:
                geolocator = Nominatim(user_agent="sobap_bot")
                location = geolocator.geocode(new_addr)
                if location:
                    payload = {
                        "action": "add", 
                        "lat": location.latitude, 
                        "lon": location.longitude, 
                        "owner": new_owner
                    }
                    requests.post(API_URL, data=json.dumps(payload))
                    st.success(f"✅ '{new_owner}' 지점이 성공적으로 등록되었습니다!")
                else:
                    st.error("주소를 찾을 수 없습니다. 정확한 주소를 입력해주세요.")
            else:
                st.warning("이름과 주소를 모두 입력해주세요.")

# --- [3] 데이터 관리 (수정/삭제) ---
elif menu == "📊 데이터 관리(수정/삭제)":
    st.title("📊 전체 데이터 관리")
    st.write("표에서 직접 내용을 수정하거나 줄을 삭제한 후 아래 저장 버튼을 누르세요.")
    
    df = get_data()
    # 데이터 에디터 출력
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    
    if st.button("변경사항 시트에 저장하기"):
        # 헤더를 포함하여 전체 데이터를 리스트 형식으로 변환
        full_data = [edited_df.columns.tolist()] + edited_df.values.tolist()
        payload = {"action": "sync", "data": full_data}
        try:
            requests.post(API_URL, data=json.dumps(payload))
            st.success("✅ 구글 시트 데이터가 성공적으로 업데이트되었습니다!")
        except Exception as e:
            st.error(f"저장 실패: {e}")
