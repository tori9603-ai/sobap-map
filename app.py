import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim

# 1. 페이지 설정 (넓게 보기)
st.set_page_config(page_title="소중한밥상 마스터 관리자", layout="wide")

# 2. 구글 앱 스크립트 URL
API_URL = "https://script.google.com/macros/s/AKfycbxmLywtQIA-6Ay5_KczYt3zNIoGekzkdWD4I3X80PORIMw8gUNHMsZTvip8LXdopxTJ/exec"

# --- 데이터 불러오기 함수 ---
def get_data():
    try:
        response = requests.get(API_URL, allow_redirects=True)
        data = response.json()
        if len(data) > 0:
            return pd.DataFrame(data[1:], columns=data[0])
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])
    except:
        return pd.DataFrame(columns=['lat', 'lon', 'owner'])

df = get_data()

# =========================================================
# 🍱 왼쪽 사이드바: 모든 관리 기능 통합
# =========================================================
with st.sidebar:
    st.title("🍱 관리자 메뉴")
    st.write("여기서 지점을 검색하고 관리하세요.")
    
    # --- [1] 지점 검색 ---
    st.subheader("🔍 지점 검색")
    search_q = st.text_input("검색어를 입력하세요", placeholder="지점명 또는 점주 이름")
    
    # 검색 필터 적용
    filtered_df = df.copy()
    if search_q:
        filtered_df = df[df['owner'].astype(str).str.contains(search_q, na=False)]
    
    st.markdown("---")
    
    # --- [2] 지점 추가 (펼치기 메뉴) ---
    with st.expander("➕ 신규 지점 등록"):
        with st.form("add_form", clear_on_submit=True):
            new_owner = st.text_input("지점/점주 이름")
            new_addr = st.text_input("지점 주소")
            if st.form_submit_button("등록"):
                if new_owner and new_addr:
                    geolocator = Nominatim(user_agent="sobap_bot")
                    location = geolocator.geocode(new_addr)
                    if location:
                        payload = {"action": "add", "lat": location.latitude, "lon": location.longitude, "owner": new_owner}
                        requests.post(API_URL, data=json.dumps(payload))
                        st.success(f"'{new_owner}' 등록 완료!")
                        st.rerun() # 등록 후 즉시 반영
                    else:
                        st.error("주소를 찾을 수 없습니다.")
                else:
                    st.warning("이름과 주소를 입력하세요.")

    # --- [3] 데이터 관리 (수정/삭제 펼치기 메뉴) ---
    with st.expander("⚙️ 데이터 수정 및 삭제"):
        st.write("표에서 직접 수정 후 아래 버튼을 누르세요.")
        edited_df = st.data_editor(df, num_rows="dynamic", hide_index=True)
        if st.button("💾 변경사항 시트에 저장"):
            full_data = [edited_df.columns.tolist()] + edited_df.values.tolist()
            payload = {"action": "sync", "data": full_data}
            requests.post(API_URL, data=json.dumps(payload))
            st.success("데이터가 업데이트되었습니다!")
            st.rerun()

# =========================================================
# 🗺️ 오른쪽 메인 화면: 지도 고정 출력
# =========================================================
st.title("🗺️ 소중한밥상 실시간 대동여지도")

# 지도 생성
m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)

# 검색 결과가 있을 때만 마커 표시
if not filtered_df.empty:
    for _, row in filtered_df.iterrows():
        try:
            folium.Marker(
                location=[float(row['lat']), float(row['lon'])],
                popup=str(row['owner']),
                tooltip=str(row['owner'])
            ).add_to(m)
        except: pass
    
    # 검색 결과 수 표시
    st.info(f"현재 {len(filtered_df)}개의 지점이 지도에 표시되고 있습니다.")
else:
    st.warning("데이터가 없거나 검색 결과가 없습니다.")

# 지도 출력
st_folium(m, width="100%", height=700)
