import streamlit as st
import folium
from streamlit_folium import st_folium
import gspread
import base64
import json
import pandas as pd
from geopy.geocoders import Nominatim

st.set_page_config(page_title="소중한밥상 마스터 관리자", layout="wide")

# --- [1] 구글 시트 연결 함수 ---
@st.cache_resource
def init_connection():
    try:
        encoded_json = st.secrets["GCP_JSON_BASE64"]
        decoded_json = base64.b64decode(encoded_json).decode("utf-8")
        creds_dict = json.loads(decoded_json)
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        gc = gspread.service_account_from_dict(creds_dict)
        return gc.open_by_key("1qedzH0zHJ3H5LCaj6XubfVOXyWj_5oBeH31uj-vNuDA")
    except Exception as e:
        st.error(f"연결 에러: {e}")
        return None

sh = init_connection()

# --- [2] 사이드바 메뉴 ---
st.sidebar.title("🍱 관리자 메뉴")
menu = st.sidebar.selectbox("기능 선택", ["🗺️ 지도 보기 및 검색", "👥 점주 추가/수정", "📊 전체 데이터 관리"])

# --- [3] 기능 구현 ---
if sh:
    wks = sh.get_worksheet(0) # 첫 번째 시트

    if menu == "🗺️ 지도 보기 및 검색":
        st.title("🗺️ 소중한밥상 '대동여지도'")
        df = pd.DataFrame(wks.get_all_records())
        
        # 검색 기능
        search_q = st.sidebar.text_input("📍 지점명 또는 점주 검색")
        if search_q:
            df = df[df['owner'].str.contains(search_q, na=False)]
            st.sidebar.write(f"검색 결과: {len(df)}건")

        m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
        for _, row in df.iterrows():
            try:
                folium.Marker([float(row['lat']), float(row['lon'])], popup=str(row['owner'])).add_to(m)
            except: pass
        st_folium(m, width="100%", height=600)

    elif menu == "👥 점주 추가/수정":
        st.title("👥 신규 지점 등록 및 수정")
        with st.form("add_form"):
            new_owner = st.text_input("지점/점주 이름")
            new_addr = st.text_input("지점 주소 (예: 부산시 해운대구 ...)")
            submitted = st.form_submit_button("지점 등록하기")
            
            if submitted:
                geolocator = Nominatim(user_agent="sobap_bot")
                location = geolocator.geocode(new_addr)
                if location:
                    wks.append_row([location.latitude, location.longitude, new_owner])
                    st.success(f"✅ {new_owner} 지점이 등록되었습니다!")
                    st.cache_data.clear()
                else:
                    st.error("주소를 찾을 수 없습니다. 다시 확인해 주세요.")

    elif menu == "📊 전체 데이터 관리":
        st.title("📊 데이터 수정 및 삭제")
        df = pd.DataFrame(wks.get_all_records())
        
        # 데이터 수정용 인터페이스
        edited_df = st.data_editor(df, num_rows="dynamic")
        
        if st.button("변경사항 저장하기"):
            wks.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
            st.success("✅ 시트 데이터가 업데이트되었습니다!")
            st.cache_data.clear()

else:
    st.error("구글 시트 연결에 실패했습니다. Secrets를 다시 확인해 주세요.")
