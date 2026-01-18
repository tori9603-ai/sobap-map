import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
from geopy.geocoders import Nominatim

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 대동여지도", layout="wide")

# 2. 사장님의 시트 ID 및 데이터 경로 (ID 입력 완료)
SHEET_ID = "1qedzH0zHJ3H5LCaj6XubfVOXyWj_5oBeH31uj-vNuDA"
# 탭 이름에 따라 데이터를 가져오는 경로를 설정합니다.
MAP_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Sheet1"
OWNER_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=owners"

# --- 사이드바 메뉴 구성 ---
st.sidebar.title("🍱 관리 메뉴")
menu = st.sidebar.radio("원하시는 작업을 선택하세요", ["🗺️ 지도 보기", "👥 점주 목록", "📍 좌표 찾기"])

# --- 데이터 로드 함수 ---
@st.cache_data(ttl=5)
def load_data(url):
    try:
        return pd.read_csv(url)
    except:
        return None

# --- [메뉴 1] 지도 보기 ---
if menu == "🗺️ 지도 보기":
    st.title("🗺️ 소중한밥상 '대동여지도'")
    df = load_data(MAP_URL)
    
    if df is not None:
        m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
        for _, row in df.iterrows():
            try:
                folium.Marker(
                    location=[float(row['lat']), float(row['lon'])],
                    popup=str(row['owner']),
                    tooltip=str(row['owner'])
                ).add_to(m)
            except: pass
        st_folium(m, width="100%", height=600)
        st.success("✅ 실시간 지도 데이터 연동 중입니다.")

# --- [메뉴 2] 점주 목록 ---
elif menu == "👥 점주 목록":
    st.title("👥 등록된 점주 현황")
    st.info("구글 시트의 'owners' 탭에 이름을 입력하면 자동으로 업데이트됩니다.")
    df_owner = load_data(OWNER_URL)
    
    if df_owner is not None:
        st.dataframe(df_owner, use_container_width=True)
    else:
        st.error("구글 시트에 'owners'라는 이름의 탭이 있는지 확인해 주세요.")

# --- [메뉴 3] 좌표 찾기 ---
elif menu == "📍 좌표 찾기":
    st.title("📍 신규 지점 좌표 찾기")
    address = st.text_input("지점 주소를 입력하세요 (예: 부산시 해운대구 ...)")
    if st.button("좌표 추출"):
        geolocator = Nominatim(user_agent="sobap_map")
        location = geolocator.geocode(address)
        if location:
            st.success("좌표를 찾았습니다!")
            st.write(f"위도(lat): `{location.latitude}`")
            st.write(f"경도(lon): `{location.longitude}`")
            st.info("이 숫자를 구글 시트의 lat, lon 칸에 넣어주세요.")
        else:
            st.error("주소를 찾을 수 없습니다.")
