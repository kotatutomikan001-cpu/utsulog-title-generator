import base64
from collections import Counter
import io
import os
import random
import shutil
import time
import urllib.parse
import urllib.request
from janome.tokenizer import Tokenizer
from PIL import Image, ImageDraw, ImageFont
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
# ★ 日本語フォント取得関数（文字化け対策）
# -------------------------------------------------------------
@st.cache_resource
def get_japanese_font():
    font_path = "NotoSansJP-Bold.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/google/fonts/raw/main/ofl/notosansjp/NotoSansJP-Bold.ttf"
        try:
            urllib.request.urlretrieve(url, font_path)
        except Exception:
            return None
    return font_path


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
    
    /* Xシェア用カスタムリンクボタン */
    .x-share-btn {{
        display: inline-block;
        background-color: #000000;
        color: #ffffff !important;
        font-weight: bold;
        padding: 0.6rem 1.2rem;
        border-radius: 8px;
        text-decoration: none;
        text-align: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }}
    .x-share-btn:hover {{
        background-color: #333333;
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
        <h1>❄️ うつログ 二つ名自動生成ソフト 🖋️</h1>
        <p>@から始まる投稿者名を入力してボタンを押すと、過去コメントの言葉の傾向を解析して<br>「二つ名」を自動生成します、どんな二つ名が飛び出すかな？</p>
        <div class="notice-text">
            ※検索機能をお借りしているうつログのサーバー負荷軽減および処理時間短縮のため、解析件数を選択できるようにしています。
        </div>
    </div>
""",
    unsafe_allow_html=True,
)


# -------------------------------------------------------------
# 2. コメント取得関数
# -------------------------------------------------------------
def fetch_comments_web(author_name, max_scrolls=5, scroll_delay=0.5):
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
            time.sleep(1.2)
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
                time.sleep(0.5)
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
        "もの",
        "ほう",
        "明日",
    }

    allowed_subcategories = [
        "一般",
        "固有名詞",
        "サ変接続",
        "形容動詞語幹",
        "ナイ形容詞語幹",
    ]

    for comment in comments:
        for token in tokenizer.tokenize(comment):
            pos_details = token.part_of_speech.split(",")
            pos_main = pos_details[0]
            pos_sub = pos_details[1]

            if pos_main == "名詞":
                if pos_sub in allowed_subcategories or pos_sub == "*":
                    word = token.base_form
                    if len(word) > 1 and word not in stop_words:
                        words.append(word)
            elif pos_main == "カスタム名詞" or pos_main == "未知語":
                word = token.surface
                if len(word) > 1 and word not in stop_words:
                    words.append(word)

    word_counts = Counter(words)
    top_words = word_counts.most_common(5)

    if not top_words:
        return "【静寂を愛する雪原の通行人】", top_words

    top1, count1 = top_words[0]
    top2 = (
        top_words[1][0]
        if len(top_words) > 1
        else ("言葉" if top1 != "言葉" else "話題")
    )

    if count1 >= 50:
        templates = [
            f"【雪月花を統べし{top1}と{top2}の絶対神】",
            f"【銀世界に降臨せし{top1}と{top2}の創世主】",
            f"【凍てつく世界を統べる{top1}と{top2}の支配者】",
            f"【氷の結晶が導く{top1}と{top2}の全知全能】",
        ]
    elif count1 >= 30:
        templates = [
            f"【氷華咲き誇る{top1}と{top2}の覇王】",
            f"【星めぐりの空に輝く{top1}と{top2}の英雄】",
            f"【氷室の深淵にて{top1}と{top2}を極めし者】",
            f"【白銀の領域を統べる{top1}と{top2}の主】",
        ]
    elif count1 >= 15:
        templates = [
            f"【凍てつく夜に輝く{top1}と{top2}の探求者】",
            f"【うつろの雪原を拓く{top1}と{top2}のマスター】",
            f"【星めぐりの学園に響く{top1}と{top2}の物語】",
            f"【静寂の氷晶に{top1}と{top2}を紡ぐ者】",
        ]
    else:
        templates = [
            f"【うつろの雪原に舞い降りし{top1}と{top2}の新星】",
            f"【かすかな粉雪のように揺れる{top1}と{top2}の愛好家】",
            f"【ひんやり優しく{top1}と{top2}を語る者】",
            f"【氷室の風に乗せて{top1}と{top2}を届ける者】",
        ]

    selected_title = random.choice(templates)
    return selected_title, top_words


# -------------------------------------------------------------
# ★ 名刺画像生成関数 (日本語フォント読み込み対応)
# -------------------------------------------------------------
def create_card_image(author_name, title, top_words):
    width, height = 1000, 560
    img = Image.new("RGB", (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    # 枠線
    draw.rectangle(
        [20, 20, width - 20, height - 20], outline=(51, 65, 85), width=3
    )
    draw.rectangle(
        [26, 26, width - 26, height - 26], outline=(148, 163, 184), width=1
    )

    font_path = get_japanese_font()

    try:
        font_header = (
            ImageFont.truetype(font_path, 22)
            if font_path
            else ImageFont.load_default()
        )
        font_author = (
            ImageFont.truetype(font_path, 32)
            if font_path
            else ImageFont.load_default()
        )
        font_title = (
            ImageFont.truetype(font_path, 34)
            if font_path
            else ImageFont.load_default()
        )
        font_rank_head = (
            ImageFont.truetype(font_path, 24)
            if font_path
            else ImageFont.load_default()
        )
        font_rank_item = (
            ImageFont.truetype(font_path, 22)
            if font_path
            else ImageFont.load_default()
        )
        font_footer = (
            ImageFont.truetype(font_path, 18)
            if font_path
            else ImageFont.load_default()
        )
    except Exception:
        font_header = font_author = font_title = font_rank_head = (
            font_rank_item
        ) = font_footer = ImageFont.load_default()

    # ヘッダーテキスト
    draw.text(
        (50, 45), "うつログ 獲得称号名刺", fill=(148, 163, 184), font=font_header
    )
    draw.text(
        (50, 85),
        f"投稿者: {author_name}",
        fill=(248, 250, 252),
        font=font_author,
    )

    # 二つ名（赤枠アクセント）
    draw.rectangle([50, 145, width - 50, 235], fill=(30, 41, 59))
    draw.text((70, 168), title, fill=(244, 63, 94), font=font_title)

    # 特徴的単語Top 3
    draw.text(
        (50, 265),
        "📊 特徴的な名詞ランキング",
        fill=(226, 232, 240),
        font=font_rank_head,
    )
    y_pos = 310
    for idx, (word, count) in enumerate(top_words[:3], 1):
        draw.text(
            (70, y_pos),
            f"第 {idx} 位:  {word}  ({count} 回)",
            fill=(203, 213, 225),
            font=font_rank_item,
        )
        y_pos += 42

    # フッター
    draw.text(
        (50, 490),
        "#うつログ二つ名ジェネレーター  |  氷室うつろ非公式ファンツール",
        fill=(100, 116, 139),
        font=font_footer,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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

        if "爆速" in mode:
            max_s = 5
            delay = 0.5
        else:
            max_s = 30
            delay = 0.9

        with st.spinner("うつログにアクセス中..."):
            comments = fetch_comments_web(
                target_author, max_scrolls=max_s, scroll_delay=delay
            )

        if comments:
            st.success(f"解析完了！ （対象コメント数: {len(comments)}件）")

            title, top_words = generate_nickname(comments)

            st.markdown("---")
            st.subheader(f"🏷️ `{target_author}` の獲得称号")
            st.header(f":red[{title}]")
            st.markdown("---")

            st.subheader("📊 特徴的な名詞ランキング（Top 5）")
            for rank_num, (word, count) in enumerate(top_words, 1):
                st.write(f"**第 {rank_num} 位**: `{word}` （{count} 回出現）")

            st.markdown("---")

            # ★ 名刺画像プレビュー ＆ ダウンロード ＆ X投稿エリア
            st.subheader("🎴 獲得称号名刺")

            # 名刺画像の生成
            img_bytes = create_card_image(target_author, title, top_words)

            # 画面上に名刺画像をプレビュー表示！（修正箇所）
            st.image(
                img_bytes,
                caption="生成された称号名刺カード",
                use_container_width=True,
            )

            st.write("")

            btn_col1, btn_col2 = st.columns([1, 1])

            with btn_col1:
                st.download_button(
                    label="💾 名刺画像を保存する",
                    data=img_bytes,
                    file_name=f"utsulog_card_{target_author}.png",
                    mime="image/png",
                    use_container_width=True,
                )

            with btn_col2:
                tweet_text = (
                    f"{target_author} の獲得称号は…\n\n"
                    f"✨ {title} ✨\n\n"
                    f"#うつログ二つ名ジェネレーター #氷室うつろ\n"
                )
                tweet_url = f"https://twitter.com/intent/tweet?text={urllib.parse.quote(tweet_text)}"

                st.markdown(
                    f'<a href="{tweet_url}" target="_blank" class="x-share-btn" style="width: 100%; display: block; text-align: center;">𝕏 に称号をポストする</a>',
                    unsafe_allow_html=True,
                )

        else:
            st.error(
                "コメントが取得できませんでした。投稿者名を確認してください。"
            )
    else:
        st.warning("投稿者名を入力してね！")
