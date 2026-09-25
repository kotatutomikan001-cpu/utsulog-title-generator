import base64
from collections import Counter
import os
import random
import shutil
import time
from janome.tokenizer import Tokenizer
from playwright.sync_api import sync_playwright
import streamlit as st

# -------------------------------------------------------------
# 1. 画面デザイン・タイトルの設定
# -------------------------------------------------------------
st.set_page_config(
    page_title="うつログ 二つ名ジェネレーター",
    page_icon="❄️",
    layout="centered",
)


# -------------------------------------------------------------
# ★ 背景画像・CSSのデザイン設定
# -------------------------------------------------------------
def set_bg_image():
    image_file = None
    mime_type = "image/png"

    if os.path.exists("bg.png"):
        image_file = "bg.png"
        mime_type = "image/png"
    elif os.path.exists("bg.jpg"):
        image_file = "bg.jpg"
        mime_type = "image/jpeg"

    bg_style = ""
    if image_file:
        with open(image_file, "rb") as f:
            encoded_string = base64.b64encode(f.read()).decode()
        bg_style = f'background-image: url("data:{mime_type};base64,{encoded_string}") !important;'
    else:
        bg_style = "background: linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%) !important;"

    css = f"""
    <style>
    /* 全体背景 */
    .stApp {{
        {bg_style}
        background-size: cover !important;
        background-position: center !important;
        background-attachment: fixed !important;
    }}
    
    [data-testid="stHeader"] {{
        background-color: rgba(0,0,0,0) !important;
    }}
    
    /* メインエリア幅 */
    .main .block-container {{
        max-width: 720px !important;
        padding-top: 2rem !important;
    }}

    /* タイトル〜注意書きを入れる黒ウィンドウ枠 */
    .header-box {{
        background-color: rgba(15, 23, 42, 0.92) !important;
        color: #ffffff !important;
        padding: 2rem !important;
        border-radius: 16px !important;
        border: 2px solid #334155 !important;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3) !important;
        margin-bottom: 1.5rem !important;
    }}

    .header-box h1 {{
        color: #f8fafc !important;
        font-size: 1.8rem !important;
        margin-bottom: 1rem !important;
    }}

    .header-box p {{
        color: #e2e8f0 !important;
        font-size: 0.95rem !important;
        line-height: 1.7 !important;
        margin-bottom: 0.8rem !important;
    }}

    .header-box .notice-text {{
        color: #94a3b8 !important;
        font-size: 0.85rem !important;
        line-height: 1.5 !important;
        border-top: 1px solid #334155;
        padding-top: 0.8rem;
        margin-top: 0.8rem;
    }}

    /* 入力フォーム枠を背景画像の上でも見やすくする白枠 */
    div[data-testid="stTextInput"], div[data-testid="stRadio"], div[data-testid="stButton"] {{
        background-color: rgba(255, 255, 255, 0.9) !important;
        padding: 1rem !important;
        border-radius: 12px !important;
        margin-bottom: 1rem !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1) !important;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# 背景デザインの適用
set_bg_image()

# -------------------------------------------------------------
# ★ 黒背景枠の中に入れるタイトル・案内文章エリア
# -------------------------------------------------------------
st.markdown(
    """
    <div class="header-box">
        <h1>❄️ うつログ 二つ名自動生成ソフト 🖊️</h1>
        <p>@から始まる投稿者名を入力してボタンを押すと、過去コメントの言葉の傾向を解析して<br>「二つ名」を自動生成します、どんな二つ名が飛び出すかな？</p>
        <div class="notice-text">
            ※検索機能をお借りしているうつログのサーバー負荷軽減および処理時間短縮のため、解析件数を選択できるようにしています。
        </div>
    </div>
""",
    unsafe_allow_html=True,
)


# -------------------------------------------------------------
# 2. コメント取得関数 (モード選択対応版)
# -------------------------------------------------------------
def fetch_comments_web(author_name, max_scrolls=30, scroll_delay=1.0):
    url = "https://utsulog.in"
    comments = []

    with sync_playwright() as p:
        chromium_path = (
            shutil.which("chromium")
            or shutil.which("chromium-browser")
            or "/usr/bin/chromium"
        )

        if os.path.exists(chromium_path):
            browser = p.chromium.launch(
                headless=True,
                executable_path=chromium_path,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
        else:
            browser = p.chromium.launch(headless=True)

        context = browser.new_context()
        page = context.new_page()

        # 画像のみ遮断して軽量化
        page.route(
            "**/*.{png,jpg,jpeg,gif,svg,webp}", lambda route: route.abort()
        )

        page.goto(url, wait_until="domcontentloaded")

        try:
            author_input = page.locator(
                'input[placeholder*="hiroki"], input[name*="author"]'
            ).first
            if not author_input.is_visible():
                author_input = page.locator(
                    'input:not([placeholder*="キーワード"])'
                ).first

            author_input.fill(author_name)
            author_input.press("Enter")
            time.sleep(1.5)
        except Exception:
            browser.close()
            return []

        prev_count = 0
        same_count_turns = 0

        progress_bar = st.progress(0)
        status_text = st.empty()

        for i in range(max_scrolls):
            comment_elements = page.query_selector_all("p.text-slate-700")
            current_count = len(comment_elements)

            progress = int(((i + 1) / max_scrolls) * 100)
            progress_bar.progress(progress)
            status_text.text(
                f"データ収集・スクロール中... ({current_count}件取得済み)"
            )

            if current_count == 0:
                time.sleep(0.8)
                continue

            if current_count == prev_count:
                same_count_turns += 1
                if same_count_turns >= 3:
                    break
            else:
                same_count_turns = 0

            prev_count = current_count

            last_elem = comment_elements[-1]
            last_elem.scroll_into_view_if_needed()
            page.keyboard.press("PageDown")
            time.sleep(scroll_delay)

        final_elements = page.query_selector_all("p.text-slate-700")
        for elem in final_elements:
            text = elem.inner_text().strip()
            if text and text not in comments:
                comments.append(text)

        status_text.empty()
        progress_bar.empty()
        browser.close()

    return comments


# -------------------------------------------------------------
# 3. 二つ名生成関数
# -------------------------------------------------------------
def generate_nickname(comments):
    tokenizer = Tokenizer()
    words = []

    stop_words = {
        "こと",
        "よう",
        "そう",
        "これ",
        "それ",
        "あれ",
        "どれ",
        "今日",
        "次回",
        "自分",
        "やつ",
        "なん",
        "ため",
        "さん",
        "ちゃん",
        "うつろ",
        "配信",
        "思い",
        "感じ",
        "いい",
        "ある",
        "する",
        "居る",
        "ない",
        "みたい",
        "んじゃ",
        "はず",
        "分け",
        "どこ",
        "そこ",
        "あっち",
        "こっち",
        "時間",
        "気",
        "お疲れ様",
        "あり",
        "なし",
        "うち",
        "どこか",
        "そこら",
        "好き",
        "もの",
        "ほう",
        "明日",
    }

    for comment in comments:
        for token in tokenizer.tokenize(comment):
            pos_details = token.part_of_speech.split(",")
            pos_main = pos_details[0]
            pos_sub = pos_details[1]

            if pos_main == "名詞" and pos_sub not in [
                "非自立",
                "代名詞",
                "数",
            ]:
                word = token.base_form
                if len(word) > 1 and word not in stop_words:
                    words.append(word)

    word_counts = Counter(words)
    top_words = word_counts.most_common(5)

    if not top_words:
        return "【無口な通行人】", "BEGINNER", "14回以下", []

    top1, count1 = top_words[0]
    top2 = (
        top_words[1][0]
        if len(top_words) > 1
        else ("言葉" if top1 != "言葉" else "話題")
    )

    if count1 >= 50:
        rank = "【GOD級】"
        rank_range = "50回以上"
        templates = [
            f"【{top1}と{top2}を統べし絶対神】",
            f"【神域に至りし{top1}と{top2}の創世主】",
            f"【{top1}を世界に刻む{top2}の全知全能】",
        ]
    elif count1 >= 30:
        rank = "【LEGEND級】"
        rank_range = "30〜49回"
        templates = [
            f"【{top1}と{top2}を極めし覇王】",
            f"【伝説の{top1}と{top2}の支配者】",
            f"【{top1}を語り継ぐ{top2}の英雄】",
        ]
    elif count1 >= 15:
        rank = "【MASTER級】"
        rank_range = "15〜29回"
        templates = [
            f"【{top1}と{top2}の探求者】",
            f"【{top1}溢れる{top2}のマスター】",
            f"【{top1}と{top2}を紡ぐ者】",
        ]
    else:
        rank = "【BEGINNER級】"
        rank_range = "14回以下"
        templates = [
            f"【ささやかな{top1}と{top2}の愛好家】",
            f"【{top1}と{top2}に魅せられし新星】",
            f"【{top1}と{top2}を語りし者】",
        ]

    selected_title = random.choice(templates)
    return selected_title, rank, rank_range, top_words


# -------------------------------------------------------------
# 4. 画面上の操作UI部分
# -------------------------------------------------------------
input_name = st.text_input(
    "投稿者名を入力してください（@以降のユーザー名）",
    value="",
    placeholder="@ユーザー名を入力",
)

mode = st.radio(
    "解析モードを選択してください",
    options=["⚡ 爆速モード（直近〜500件程度）", "🐢 じっくり解析モード（直近〜3000件程度）"],
    index=0,
)

col1, col2 = st.columns([1, 1])

with col1:
    generate_btn = st.button(
        "二つ名を自動生成する！", type="primary", use_container_width=True
    )

if generate_btn:
    raw_author = input_name.strip()
    if raw_author:
        target_author = (
            raw_author if raw_author.startswith("@") else f"@{raw_author}"
        )

        # モードに応じた設定の分岐
        if "爆速" in mode:
            max_s = 15
            delay = 0.6
        else:
            max_s = 40
            delay = 1.0

        with st.spinner("うつログにアクセス中..."):
            comments = fetch_comments_web(
                target_author, max_scrolls=max_s, scroll_delay=delay
            )

        if comments:
            st.success(f"解析完了！ （対象コメント数: {len(comments)}件）")

            title, rank, rank_range, top_words = generate_nickname(comments)

            st.markdown("---")
            st.subheader(f"🏷️ `{target_author}` の獲得称号")
            st.caption(
                f"称号ランク: **{rank}** (1位単語出現回数 {rank_range})"
            )
            st.header(f":red[{title}]")
            st.markdown("---")

            st.subheader("📊 特徴的な名詞ランキング（Top 5）")
            for rank_num, (word, count) in enumerate(top_words, 1):
                st.write(f"**第 {rank_num} 位**: `{word}` （{count} 回出現）")

        else:
            st.error(
                "コメントが取得できませんでした。投稿者名を確認してください。"
            )
    else:
        st.warning("投稿者名を入力してね！")
