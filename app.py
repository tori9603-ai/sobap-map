import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
from geopy.geocoders import Nominatim

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 대동여지도", layout="wide")

# 2. 사장님의 시트 ID (입력 완료)
SHEET_ID = "1qedzH0zHJ3H5LCaj6XubfVOXyWj_5oBeH31uj-vNuDA"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

st.title("🗺️ 소중한밥상 '대동여지도'")

# --- 사이드바: 주소 찾기 도구 ---
with st.sidebar:
    st.header("📍 신규 지점 좌표 찾기")
    st.write("주소를 입력하면 위도와 경도를 알려줍니다.")
    address = st.text_input("지점 주소를 입력하세요 (예: 서울시 중구 세종대로 110)")
    
    if st.button("좌표 찾기"):
        geolocator = Nominatim(user_agent="sobap_map")
        location = geolocator.geocode(address)
        if location:
            st.success(f"찾았습니다!")
            st.code(f"위도(lat): {location.latitude}\n경도(lon): {location.longitude}")
            st.info("이 숫자를 구글 시트의 lat, lon 칸에 복사해 넣으세요.")
        else:
            st.error("주소를 찾을 수 없습니다. 정확한 주소를 입력해주세요.")

# --- 메인 화면: 지도 표시 ---
@st.cache_data(ttl=5)
def load_data():
    try:
        # 시트를 직접 CSV로 읽어옵니다.
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        st.error(f"❌ 데이터를 가져오지 못했습니다. 시트의 [공유] 설정이 '편집자'로 되어있는지 확인하세요.\n에러: {e}")
        return None

df = load_data()

if df is not None:
    # 데이터 확인용 (지도가 안 뜰 때 확인용)
    with st.expander("데이터 미리보기"):
        st.write(df)

    # 서울 중심 지도 생성
    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
    
    # 지점 마커 찍기
    for _, row in df.iterrows():
        try:
            # 시트에 'lat', 'lon', 'owner' 컬럼명이 정확히 있어야 합니다.
            folium.Marker(
                location=[float(row['lat']), float(row['lon'])],
                popup=str(row['owner']),
                tooltip=str(row['owner'])
            ).add_to(m)
        except:
            pass
            
    st_folium(m, width="100%", height=600)
    st.success("✅ 지도가 성공적으로 연결되었습니다!")
