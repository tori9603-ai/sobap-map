import streamlit as st
import folium
from streamlit_folium import st_folium
import gspread

st.set_page_config(page_title="대동여지도", layout="wide")

@st.cache_resource
def init_connection():
    try:
        # 하나씩 나열된 Secrets 정보를 딕셔너리로 합칩니다.
        creds_dict = {
            "type": st.secrets["gcp_type"],
            "project_id": st.secrets["gcp_project_id"],
            "private_key_id": st.secrets["gcp_private_key_id"],
            "private_key": st.secrets["gcp_private_key"].replace("\\n", "\n"),
            "client_email": st.secrets["gcp_client_email"],
            "client_id": st.secrets["gcp_client_id"],
            "auth_uri": st.secrets["gcp_auth_uri"],
            "token_uri": st.secrets["gcp_token_uri"],
            "auth_provider_x509_cert_url": st.secrets["gcp_auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["gcp_client_x509_cert_url"],
            "universe_domain": st.secrets["gcp_universe_domain"],
        }
        gc = gspread.service_account_from_dict(creds_dict)
        return gc.open("map_data")
    except Exception as e:
        st.error(f"❌ 연결 에러: {e}")
        return None

sh = init_connection()

st.title("🗺️ 소중한밥상 '대동여지도'")
if sh:
    try:
        data = sh.get_worksheet(0).get_all_records()
        m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
        for t in data:
            try:
                folium.Marker([float(t['lat']), float(t['lon'])], popup=str(t['owner'])).add_to(m)
            except: pass
        st_folium(m, width="100%", height=600)
        st.success("✅ 지도 연동 성공!")
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
