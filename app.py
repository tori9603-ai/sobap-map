import streamlit as st
import folium
from streamlit_folium import st_folium
import gspread

# 1. 페이지 설정
st.set_page_config(page_title="대동여지도", layout="wide")

# =========================================================
# ☁️ [구글 시트 연결] - Secrets 데이터를 읽어와서 연결
# =========================================================
@st.cache_resource
def init_connection():
    try:
        # Secrets에서 정보를 딕셔너리로 읽어옵니다.
        if "gcp_service_account" not in st.secrets:
            st.error("Secrets 설정이 누락되었습니다. 1단계를 다시 확인해주세요.")
            return None
            
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # ⚠️ 줄바꿈 기호(\n)가 문자열로 인식된 경우를 대비해 정상화합니다.
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n").strip()
            
        # 인증 정보를 사용하여 구글 시트에 접속합니다.
        gc = gspread.service_account_from_dict(creds_dict)
        sh = gc.open("map_data")
        return sh
    except Exception as e:
        st.error(f"구글 시트 연결 실패! 에러 내용: {e}")
        return None

sh = init_connection()

# =========================================================
# 📍 지도 표시 및 데이터 렌더링
# =========================================================
st.title("🗺️ 대동여지도")
st.caption("✅ 구글 스프레드시트와 실시간 연동 중입니다.")

if sh:
    try:
        # 첫 번째 시트의 데이터를 모두 가져옵니다.
        wks = sh.get_worksheet(0)
        data = wks.get_all_records()
        
        # 서울 중심 기본 지도 생성 (위도: 37.5665, 경도: 126.9780)
        m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
        
        # 시트에 기록된 지점들을 마커로 표시합니다.
        for item in data:
            try:
                # 시트에 'lat'(위도), 'lon'(경도) 컬럼이 있어야 합니다.
                folium.Marker(
                    [float(item['lat']), float(item['lon'])], 
                    popup=str(item.get('owner', '지점'))
                ).add_to(m)
            except:
                pass
            
        st_folium(m, width="100%", height=600)
        st.success("데이터 연동 및 지도 로드에 성공했습니다!")
        
    except Exception as e:
        st.warning(f"데이터를 불러오는 중 문제가 발생했습니다: {e}")
