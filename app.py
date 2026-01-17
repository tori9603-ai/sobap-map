import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pandas as pd
import os
import gspread
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="공동구매 지도 관리자", layout="wide")

# =========================================================
# ☁️ [구글 시트 연결]
# =========================================================
@st.cache_resource
def init_connection():
    try:
        gc = gspread.service_account(filename='service_account.json')
        sh = gc.open("map_data")
        return sh
    except Exception as e:
        st.error(f"❌ 구글 시트 연결 실패! 파일 설정을 확인하세요.\n에러: {e}")
        return None

sh = init_connection()

# [과부하 방지 수정] 시트 검사는 접속 후 딱 1번만 실행
if 'sheet_checked' not in st.session_state:
    st.session_state.sheet_checked = False

def check_and_fix_sheets():
    # 이미 검사했으면 패스 (구글 괴롭힘 방지)
    if st.session_state.sheet_checked:
        return
        
    if sh is None: return

    # owners 시트 점검
    try:
        wks = sh.worksheet("owners")
        if wks.acell('A1').value != "name":
            wks.insert_row(["name"], index=1)
    except gspread.exceptions.WorksheetNotFound:
        wks = sh.add_worksheet(title="owners", rows=100, cols=5)
        wks.update_acell('A1', 'name')

    # map_data 시트 점검
    try:
        wks_map = sh.get_worksheet(0)
        required = ["owner", "address", "lat", "lon", "bbox"]
        current_headers = wks_map.row_values(1)
        if not current_headers or current_headers != required:
             if not current_headers or current_headers[0] == "":
                 wks_map.insert_row(required, index=1)
    except: pass
    
    # 검사 완료 도장 찍기
    st.session_state.sheet_checked = True

# 실행
check_and_fix_sheets()

# [데이터 청소]
def clean_data(raw_data):
    clean_list = []
    for item in raw_data:
        if 'lat' not in item or 'lon' not in item: continue
        try:
            item['lat'] = float(item['lat'])
            item['lon'] = float(item['lon'])
            clean_list.append(item)
        except: continue
    return clean_list

# 데이터 읽기 (캐싱 적용으로 과부하 방지)
# ttl=5 : 5초 동안은 구글을 다시 부르지 않고 기억된 데이터를 씀
@st.cache_data(ttl=5)
def load_data_from_google():
    if sh is None: return [], []
    
    # 1. 지도 데이터
    try:
        wks_map = sh.get_worksheet(0)
        raw_map = wks_map.get_all_records()
        data_map = clean_data(raw_map)
    except: data_map = []
    
    # 2. 점주 목록
    try:
        wks_owners = sh.worksheet("owners")
        owners_list = wks_owners.col_values(1)[1:] 
        if not owners_list: owners_list = ["김철수 점주"]
    except:
        owners_list = ["김철수 점주"]

    return data_map, owners_list

# 데이터 로드
map_data, owners_data = load_data_from_google()
st.session_state.territories = map_data
st.session_state.owners = owners_data

if 'search_results' not in st.session_state:
    st.session_state.search_results = []

# =========================================================
# 🖼️ 화면 구성
# =========================================================
image_path = "image_5.png"
if os.path.exists(image_path):
    st.image(image_path, use_container_width=True)

st.title("🗺️ 소중한밥상 '대동여지도' (팀 공유 모드)")
st.caption("✅ 구글 스프레드시트와 실시간 연동 중입니다.")

def get_color(owner_name):
    palette = ["red", "blue", "green", "purple", "orange", "darkred", "cadetblue", "black"]
    try:
        if owner_name in st.session_state.owners:
            idx = st.session_state.owners.index(owner_name)
            return palette[idx % len(palette)]
    except: pass
    return "gray"

# 4. 사이드바
with st.sidebar:
    st.title("🔧 관리자 메뉴")
    
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear() # 캐시 비우기
        st.rerun()
        
    st.divider()
    
    # [점주 관리] 탭
    with st.expander("👥 점주 명단 관리", expanded=True):
        tab_add, tab_edit, tab_del = st.tabs(["추가", "수정", "삭제"])
        
        # 추가
        with tab_add:
            new_owner = st.text_input("새 점주 이름", key="add_new")
            if st.button("추가", key="btn_add"):
                if new_owner and new_owner not in st.session_state.owners:
                    try:
                        sh.worksheet("owners").append_row([new_owner])
                        st.success(f"'{new_owner}' 추가 완료!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"오류: {e}")
                elif new_owner in st.session_state.owners:
                    st.warning("이미 있는 이름입니다.")

        # 수정
        with tab_edit:
            if st.session_state.owners:
                target_owner = st.selectbox("이름 바꿀 점주", st.session_state.owners, key="edit_target")
                new_name = st.text_input("새로운 이름", key="edit_name")
                
                if st.button("이름 변경", key="btn_edit"):
                    if new_name and new_name not in st.session_state.owners:
                        try:
                            wks_owners = sh.worksheet("owners")
                            cell = wks_owners.find(target_owner)
                            wks_owners.update_cell(cell.row, cell.col, new_name)
                            
                            with st.spinner(f"'{target_owner}'님의 땅 명의 변경 중..."):
                                wks_map = sh.get_worksheet(0)
                                cell_list = wks_map.findall(target_owner)
                                update_list = []
                                for cell in cell_list:
                                    if cell.col == 1:
                                        cell.value = new_name
                                        update_list.append(cell)
                                if update_list:
                                    wks_map.update_cells(update_list)
                                    
                            st.success(f"변경 완료!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e: st.error(f"수정 실패: {e}")
            else:
                st.info("점주가 없습니다.")

        # 삭제
        with tab_del:
            if st.session_state.owners:
                del_target = st.selectbox("삭제할 점주", st.session_state.owners, key="del_sel")
                if st.button("삭제", key="btn_del"):
                    try:
                        wks = sh.worksheet("owners")
                        cell = wks.find(del_target)
                        wks.delete_rows(cell.row)
                        st.success("삭제 완료!")
                        st.cache_data.clear()
                        st.rerun()
                    except: st.error("삭제 실패")

    st.divider()

    # [작업 선택]
    if st.session_state.owners:
        current_owner = st.selectbox("작업할 점주 선택", st.session_state.owners)
        
        st.header(f"🚩 {current_owner} 구역 확장")
        with st.form("search"):
            q = st.text_input("주소/아파트 검색", placeholder="예: 관악 푸르지오")
            if st.form_submit_button("🔍 검색"):
                geolocator = Nominatim(user_agent="team_map_limit_fix")
                try:
                    res = geolocator.geocode(q, exactly_one=False, limit=5)
                    st.session_state.search_results = res if res else []
                except: st.error("검색 오류")

        sel_loc = None
        if st.session_state.search_results:
            st.write("👇 **리스트를 클릭하여 위치 확인**")
            opts = {f"{l.address}": l for l in st.session_state.search_results}
            sel = st.radio("검색 결과", list(opts.keys()))
            sel_loc = opts[sel]
            
            if st.button("🚩 점령 확정!", type="primary"):
                conflict = False
                msg = ""
                for t in st.session_state.territories:
                    if 'owner' not in t or 'lat' not in t: continue
                    if t['owner'] == current_owner: continue
                    try:
                        dist = geodesic((sel_loc.latitude, sel_loc.longitude), (t['lat'], t['lon'])).km
                        if dist <= 1.0:
                            conflict = True
                            msg = t['owner']
                            break
                    except: continue
                
                if conflict: st.error(f"🚫 불가! {msg}님이 1km 내에 있습니다.")
                else:
                    bbox_str = str(sel_loc.raw.get('boundingbox')) if sel_loc.raw.get('boundingbox') else ""
                    row = [current_owner, sel_loc.address, sel_loc.latitude, sel_loc.longitude, bbox_str]
                    try:
                        sh.get_worksheet(0).append_row(row)
                        st.success("✅ 서버 저장 완료!")
                        st.session_state.search_results = []
                        st.cache_data.clear() # 저장했으니 최신 데이터 불러오게 초기화
                        st.rerun()
                    except Exception as e: st.error(f"저장 실패: {e}")
                    
        # 구역 삭제
        my_territories = [t for t in st.session_state.territories if t.get('owner') == current_owner]
        if my_territories:
            st.divider()
            st.write(f"🗑️ {current_owner} 구역 삭제")
            for item in my_territories:
                c1, c2 = st.columns([3,1])
                addr_str = str(item.get('address', '주소없음')).split(',')[0]
                c1.text(addr_str)
                if c2.button("삭제", key=f"del_{addr_str}"):
                    try:
                        wks = sh.get_worksheet(0)
                        cell = wks.find(item['address'])
                        wks.delete_rows(cell.row)
                        st.success("삭제 완료")
                        st.cache_data.clear()
                        st.rerun()
                    except: st.error("삭제 실패")
    else:
        st.warning("등록된 점주가 없습니다. 먼저 점주를 추가해주세요.")

# 5. 지도 그리기
c_loc = [37.5665, 126.9780]; z = 11
if 'sel_loc' in locals() and sel_loc:
    c_loc = [sel_loc.latitude, sel_loc.longitude]; z = 16
elif st.session_state.territories:
    if len(st.session_state.territories) > 0:
        last = st.session_state.territories[-1]
        c_loc = [last['lat'], last['lon']]; z = 14

m = folium.Map(location=c_loc, zoom_start=z)

for t in st.session_state.territories:
    if 'owner' not in t or 'lat' not in t: continue
    color = get_color(t['owner'])
    folium.Marker([t['lat'], t['lon']], popup=t['owner'], icon=folium.Icon(color=color, icon="home")).add_to(m)
    try:
        if t.get('bbox'):
            import ast
            bbox_data = t['bbox']
            if isinstance(bbox_data, str) and bbox_data:
                bbox_data = ast.literal_eval(bbox_data)
            if bbox_data:
                mn_lat, mx_lat, mn_lon, mx_lon = map(float, bbox_data)
                folium.Rectangle([[mn_lat, mn_lon], [mx_lat, mx_lon]], color=color, fill=True, fill_opacity=0.5).add_to(m)
            else:
                folium.Circle([t['lat'], t['lon']], radius=100, color=color, fill=True).add_to(m)
        else:
             folium.Circle([t['lat'], t['lon']], radius=100, color=color, fill=True).add_to(m)
    except: pass

if 'sel_loc' in locals() and sel_loc:
    folium.Marker([sel_loc.latitude, sel_loc.longitude], icon=folium.Icon(color="black", icon="question-sign")).add_to(m)

st_folium(m, width="100%", height=600)