import streamlit as st
import folium
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim

# --- 1. 초기 설정 및 세션 상태 관리 ---
st.set_page_config(layout="wide", page_title="소중한밥상 관리 시스템")

# 지도 중심점 좌표 초기화 (기본값: 부산시청 부근)
if 'map_center' not in st.session_state:
    st.session_state.map_center = [35.1796, 129.0756]

# 카카오맵 API 키 설정 (나중에 승인받으면 여기에 입력하세요)
# 예: KAKAO_API_KEY = "your_api_key_here"
KAKAO_API_KEY = None 

# --- 2. 사이드바 UI (이미지 구성 반영) ---
with st.sidebar:
    st.header("🍱 소중한밥상 관리")
    st.subheader("👤 점주 관리")
    
    # 신규 점주 등록 버튼 (기능 유지용)
    if st.button("➕ 신규 점주 등록"):
        pass

    # 관리할 점주 선택
    owner_list = ["박선희", "김철수", "이영희"] # 예시 데이터
    selected_owner = st.selectbox("관리할 점주 선택", owner_list)
    
    st.write("---")
    st.subheader("📍 선점 내역")
    # 선점 내역 표시 공간 (기능 유지)
    st.info("현재 선택된 점주의 선점 내역이 여기에 표시됩니다.")

    st.write("---")
    st.subheader("2️⃣ 영업권 구역 선정")
    address_input = st.text_input("아파트명 또는 주소 입력", value="퇴계현대2차")
    
    # [핵심 수정] 위치 찾기 버튼 로직
    if st.button("🔍 위치 찾기"):
        geolocator = Nominatim(user_agent="sojunghan_bapsang_manager")
        location = geolocator.geocode(address_input)
        
        if location:
            # 좌표 업데이트 및 세션 저장
            st.session_state.map_center = [location.latitude, location.longitude]
            # 지도를 즉시 이동시키기 위해 페이지 새로고침
            st.rerun()
        else:
            st.error("주소를 찾을 수 없습니다. 다시 입력해주세요.")

# --- 3. 메인 화면: 지도 표시 로직 ---
st.title("🗺️ 소중한밥상 실시간 관제 시스템")

def render_map(center):
    """카카오맵 키 유무에 따른 듀얼 지도 렌더링"""
    if KAKAO_API_KEY:
        # 1. 카카오맵 승인 후 (HTML/JS 연동)
        kakao_map_html = f"""
        <div id="map" style="width:100%;height:600px;"></div>
        <script type="text/javascript" src="//dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_API_KEY}"></script>
        <script>
            var container = document.getElementById('map');
            var options = {{
                center: new kakao.maps.LatLng({center[0]}, {center[1]}),
                level: 3
            }};
            var map = new kakao.maps.Map(container, options);
        </script>
        """
        st.components.v1.html(kakao_map_html, height=600)
    else:
        # 2. 카카오맵 승인 전 (Folium/OSM 사용)
        # st.warning("현재는 Folium 기반의 오픈 지도를 사용 중입니다. (카카오맵 API 키 미등록)")
        m = folium.Map(location=center, zoom_start=17, control_scale=True)
        
        # 현재 중심점에 마커 표시
        folium.Marker(
            center, 
            popup=address_input,
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)
        
        # 지도 출력
        folium_static(m, width=1000, height=600)

# 지도 실행
render_map(st.session_state.map_center)
