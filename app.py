import streamlit as st
import folium
from streamlit_folium import st_folium
import gspread
import base64
import json

# 1. 페이지 설정
st.set_page_config(page_title="소중한밥상 대동여지도", layout="wide")

# =========================================================
# ☁️ [구글 시트 연결] - Base64 암호 해독 방식 (오류 해결용)
# =========================================================
@st.cache_resource
def init_connection():
    try:
        # Secrets에서 암호화된 한 문장을 가져옵니다.
        if "GCP_JSON_BASE64" not in st.secrets:
            st.error("❌ 스트림릿 Secrets 설정이 누락되었습니다. 1단계를 다시 확인하세요.")
            return None
        
        encoded_json = st.secrets["GCP_JSON_BASE64"]
        
        # ⚠️ 글자 수 오류(Multiple of 4)를 강제로 해결하는 코드
        missing_padding = len(encoded_json) % 4
        if missing_padding:
            encoded_json += '=' * (4 - missing_padding)
            
        # 암호를 풀어 JSON 딕셔너리로 변환합니다.
        decoded_json = base64.b64decode(encoded_json).decode("utf-8")
        creds_dict = json.loads(decoded_json)
        
        # 비밀번호 내 줄바꿈(\n) 기호를 정상화합니다.
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
        gc = gspread.service_account_from_dict(creds_dict)
        sh = gc.open("map_data")
        return sh
    except Exception as e:
        st.error(f"❌ 구글 시트 연결 실패! 아래 내용을 확인하세요.\n{e}")
        return None

sh = init_connection()

# =========================================================
# 📍 지도 표시
# =========================================================
st.title("🗺️ 소중한밥상 '대동여지도'")

if sh:
    try:
        wks = sh.get_worksheet(0)
        map_data = wks.get_all_records()
        
        # 서울 중심 지도 생성
        m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
        
        for t in map_data:
            try:
                folium.Marker(
                    [float(t['lat']), float(t['lon'])], 
                    popup=str(t['owner'])
                ).add_to(m)
            except: pass
            
        st_folium(m, width="100%", height=600)
        st.success("✅ 지도가 성공적으로 연결되었습니다!")
        
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
