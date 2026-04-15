import streamlit as st
import pandas as pd
from pathlib import Path
from PIL import Image
import re
import uuid
import os
import random
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="3DGS IQA Annotation", layout="wide")

st.markdown("""
<style>
    .stSlider label p { font-size: 24px !important; font-weight: bold !important; color: #333333 !important; }
    .stSlider div[data-testid="stSliderTickBarMin"], .stSlider div[data-testid="stSliderTickBarMax"] { font-size: 16px !important; }
    .stButton > button { padding: 10px 24px !important; min-height: 50px !important; }
    .stButton > button p { font-size: 22px !important; font-weight: bold !important; }
</style>
""", unsafe_allow_html=True)

os.makedirs("assets", exist_ok=True) 


@st.cache_resource
def init_gsheets():
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1A2WuW6iruRaHzK0-WmoAQksVSfV04FFwJl6iUs88B5I/edit?gid=0#gid=0").sheet1
    return sheet

def assign_least_rated_folder(sheet):
    folders = [f"Image({chr(65+i)})" for i in range(10)] 
    try:
        existing_folders = sheet.col_values(2)[1:] 
        counts = {f: existing_folders.count(f) for f in folders}
    except Exception:
        counts = {f: 0 for f in folders}
        

    min_count = min(counts.values())

    candidates = [folder for folder, count in counts.items() if count == min_count]
    
    assigned = random.choice(candidates)
    
    return assigned

# init
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]
if 'has_started' not in st.session_state:
    st.session_state.has_started = False
if 'sheet' not in st.session_state:
    st.session_state.sheet = init_gsheets()
if 'assigned_folder' not in st.session_state:
    st.session_state.assigned_folder = assign_least_rated_folder(st.session_state.sheet)
if 'current_idx' not in st.session_state:
    st.session_state.current_idx = 0
if 'ratings' not in st.session_state:
    st.session_state.ratings = {}
if 'is_submitted' not in st.session_state:
    st.session_state.is_submitted = False

def resize_and_crop(img_path, target_aspect_ratio=(16, 9), target_width=800):
    if not img_path.exists(): return None
    try:
        img = Image.open(img_path)
    except Exception:
        return None
    target_height = int(target_width * target_aspect_ratio[1] / target_aspect_ratio[0])
    orig_width, orig_height = img.size
    orig_aspect = orig_width / orig_height
    target_aspect = target_aspect_ratio[0] / target_aspect_ratio[1]

    if orig_aspect > target_aspect:
        new_height = target_height
        new_width = int(new_height * orig_aspect)
    else:
        new_width = target_width
        new_height = int(new_width / orig_aspect)
    
    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left, top = (new_width - target_width) / 2, (new_height - target_height) / 2
    right, bottom = (new_width + target_width) / 2, (new_height + target_height) / 2
    return img_resized.crop((left, top, right, bottom))


# Guideline part
if not st.session_state.has_started:
    st.title("📝 3DGS 影像品質評估 (IQA) - 評分指南")
    st.markdown("""
    ### 評分標準 (0 = 嚴重瑕疵, 10 = 無瑕疵)
    <div style="font-size: 22px; line-height: 1.6;">
        <p>對照畫面左側 Reference (參考影像)，根據以下兩個主要維度來決定每個瑕疵項目的扣分程度：</p>
        <ol>
            <li><b>瑕疵覆蓋面積</b>：瑕疵在畫面上佔據的比例越大、範圍越廣，分數應越低。</li>
            <li><b>顏色與結構差異</b>：瑕疵的顏色或形狀與 Reference 差異越明顯、在畫面上越突兀，分數應越低。</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    st.markdown("### 🖼️ 瑕疵類型圖例說明")
    
    TARGET_RATIO, TARGET_DISPLAY_WIDTH = (16, 9), 800
    
    # --- 第一排：Blur 與 Needle ---
    row1_col1, row1_col2 = st.columns(2)
    
    with row1_col1:
        st.markdown("#### 1. Blur (模糊)")
        img_blur = resize_and_crop(Path("assets/blur_example.png"), TARGET_RATIO, TARGET_DISPLAY_WIDTH)
        if img_blur: st.image(img_blur, use_container_width=True)
        st.markdown("**特徵**：細節遺失、紋理過度平滑，失去原本的銳利度。")
        
    with row1_col2:
        st.markdown("#### 2. Needle (針狀物)")
        img_needle = resize_and_crop(Path("assets/needle_example.png"), TARGET_RATIO, TARGET_DISPLAY_WIDTH)
        if img_needle: st.image(img_needle, use_container_width=True)
        st.markdown("**特徵**：物體表面或邊緣出現不自然的尖刺狀、針狀延伸。")

    st.divider() # 加入分隔線讓區塊更明確

    # --- 第二排：Floater 的兩種細分類型 ---
    st.markdown("#### 3. Floater (漂浮物 - 兩種類型說明)")
    row2_col1, row2_col2 = st.columns(2)
    
    with row2_col1:
        img_floater_1 = resize_and_crop(Path("assets/floater_type_a.png"), TARGET_RATIO, TARGET_DISPLAY_WIDTH)
        if img_floater_1: st.image(img_floater_1, use_container_width=True)
        st.markdown("**特徵**：在不該有物體的空白處出現的塊狀或點狀雜點。")
        
    with row2_col2:
        img_floater_2 = resize_and_crop(Path("assets/floater_type_b.png"), TARGET_RATIO, TARGET_DISPLAY_WIDTH)
        if img_floater_2: st.image(img_floater_2, use_container_width=True)
        st.markdown("**特徵**：Reference影像上沒有的異常顏色的霧狀瑕疵。")
        
    st.divider()
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        def start_experiment():
            st.session_state.has_started = True
        st.button("✅ 我已了解評分標準，開始進行評分", type="primary", use_container_width=True, on_click=start_experiment)
    st.stop()

if st.session_state.is_submitted:
    st.balloons()
    st.success("評分已成功送出！非常感謝您的參與。")
    st.stop() 


def get_ref_path(render_stem, ref_dir):
    if not ref_dir.exists(): return None
    m = re.match(r'^(.*?_cam\d+)\b', render_stem)
    key = m.group(1) if m else render_stem.rsplit('_', 1)[0] if '_' in render_stem else render_stem
    for p in ref_dir.iterdir():
        if key.lower() in p.stem.lower():
            return p
    return None


# 3. Load images
@st.cache_data
def load_image_list(folder_name):
    target_dir = Path("renders") / folder_name 
    refs_dir = Path("refs")
    
    if not target_dir.exists():
        return [], target_dir, refs_dir
        
    valid_exts = {".png", ".jpg", ".jpeg"}
    render_paths = sorted([p for p in target_dir.iterdir() if p.suffix.lower() in valid_exts])
    return render_paths, target_dir, refs_dir

base_render_paths, renders_dir, refs_dir = load_image_list(st.session_state.assigned_folder)

if not base_render_paths:
    st.error(f"Image not found `renders/{st.session_state.assigned_folder}` ")
    st.stop()

if 'shuffled_paths' not in st.session_state:
    paths_copy = base_render_paths.copy() 
    random.shuffle(paths_copy)           
    st.session_state.shuffled_paths = paths_copy 

render_paths = st.session_state.shuffled_paths

if not render_paths:
    st.error(f"Image not found `renders/{st.session_state.assigned_folder}` ")
    st.stop()

with st.sidebar:
    st.title("評分指南 (Guidelines)")
    st.markdown("""
    * **Floater**: 空白處出現的漂浮瑕疵或異常顏色的霧狀瑕疵。
    * **Needle**: 物體表面或邊緣出現的針狀/刺狀瑕疵。
    * **Blur**: 細節遺失、過度平滑。
    """)

idx = st.session_state.current_idx
total = len(render_paths)
current_render_path = render_paths[idx]
img_name = current_render_path.stem

st.title("3DGS Subjective IQA")
st.subheader(f"Images：{idx + 1} / {total}")

col1, col2 = st.columns(2)
with col1:
    st.markdown("### Reference")
    ref_path = get_ref_path(img_name, refs_dir)
    if ref_path and ref_path.exists():
        st.image(Image.open(ref_path), use_container_width=True)
    else:
        st.info(f" Reference not found: {img_name}")

with col2:
    st.markdown("### Render")
    st.image(Image.open(current_render_path), use_container_width=True)

st.divider()
st.markdown("### 評分 (0 = 嚴重瑕疵, 10 = 無瑕疵)")

current_ratings = st.session_state.ratings.get(img_name, {'floater': 0, 'blur': 0, 'needle': 0, 'overall': 0})

def update_rating(metric):
    if img_name not in st.session_state.ratings:
        st.session_state.ratings[img_name] = {'floater': 0, 'blur': 0, 'needle': 0, 'overall': 0}
    st.session_state.ratings[img_name][metric] = st.session_state[f"{metric}_{img_name}"]

c1, c2, c3, c4 = st.columns(4)
with c1: st.slider("Floater", 0, 10, current_ratings['floater'], key=f"floater_{img_name}", on_change=update_rating, args=('floater',))
with c2: st.slider("Blur", 0, 10, current_ratings['blur'], key=f"blur_{img_name}", on_change=update_rating, args=('blur',))
with c3: st.slider("Needle", 0, 10, current_ratings['needle'], key=f"needle_{img_name}", on_change=update_rating, args=('needle',))
with c4: st.slider("Overall", 0, 10, current_ratings['overall'], key=f"overall_{img_name}", on_change=update_rating, args=('overall',))

st.divider()

def prev_img():
    if st.session_state.current_idx > 0: st.session_state.current_idx -= 1

def next_img():
    if st.session_state.current_idx < total - 1: st.session_state.current_idx += 1

def submit_data():
    rows_to_insert = []
    for img, ratings in st.session_state.ratings.items():
        rows_to_insert.append([
            st.session_state.user_id,
            st.session_state.assigned_folder,
            img,
            ratings['floater'],
            ratings['blur'],
            ratings['needle'],
            ratings['overall']
        ])
    
    st.session_state.sheet.append_rows(rows_to_insert)
    st.session_state.is_submitted = True

btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 6])
with btn_col1: st.button("⬅️ 上一張", on_click=prev_img, disabled=(idx == 0))
with btn_col2:
    if idx == total - 1:
        st.button("送出評分", on_click=submit_data, type="primary")
    else:
        st.button("下一張 ➡️", on_click=next_img)
