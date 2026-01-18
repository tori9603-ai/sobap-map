import streamlit as st
import folium
from streamlit_folium import st_folium
import gspread

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 대동여지도", layout="wide")

# =========================================================
# ☁️ [구글 시트 연결] - 금고(Secrets) 데이터를 정돈하여 연결
# =========================================================
@st.cache_resource
def init_connection():
    try:
        # 1단계에서 저장한 금고 데이터를 가져옵니다.
        if "gcp_service_account" not in st.secrets:
            st.error("❌ 스트림릿 Secrets 설정이 누락되었습니다. 1단계를 다시 확인해주세요.")
            return None
            
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # ⚠️ 핵심 해결책: 비밀번호 내의 줄바꿈(\n)과 공백을 강제로 정돈합니다.
        raw_key = str(creds_dict.get("private_key", ""))
        creds_dict["private_key"] = raw_key.replace("\\n", "\n").replace(" ", "").strip()
        
        # BEGIN/END 문구의 띄어쓰기는 유지해야 하므로 다시 보정합니다.
        if "-----BEGINPRIVATEKEY-----" in creds_dict["private_key"]:
            creds_dict["private_key"] = creds_dict["private_key"].replace(
                "-----BEGINPRIVATEKEY-----", "-----BEGIN PRIVATE KEY-----\n"
            ).replace("-----ENDPRIVATEKEY-----", "\n-----END PRIVATE KEY-----")
            
        # 2. 정돈된 열쇠로 구글 시트에 접속합니다.
        gc = gspread.service_account_from_dict(creds_dict)
        sh = gc.open("map_data")
        return sh
    except Exception as e:
        st.error(f"❌ 구글 시트 연결 실패! 아래 에러를 확인하세요.\n{str(e)}")
        return None

sh = init_connection()

# =========================================================
# 📍 지도 표시 및 데이터 렌더링
# =========================================================
st.title("🗺️ 소중한밥상 '대동여지도'")
st.caption("✅ 구글 스프레드시트와 실시간 연동 중입니다.")

if sh:
    try:
        # 첫 번째 시트에서 지점 데이터를 가져옵니다.
        wks_map = sh.get_worksheet(0)
        map_data = wks_map.get_all_records()
        
        # 서울 중심 기본 지도 생성
        m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
        
        # 시트에 기록된 지점들을 마커로 표시합니다.
        for t in map_data:
            try:
                folium.Marker(
                    [float(t['lat']), float(t['lon'])], 
                    popup=str(t['owner'])
                ).add_to(m)
            except:
                pass
            
        st_folium(m, width="100%", height=600)
        st.success("✅ 지도가 성공적으로 로드되었습니다!")
        
    except Exception as e:
        st.warning(f"데이터를 읽어오는 중 문제가 발생했습니다: {e}")
