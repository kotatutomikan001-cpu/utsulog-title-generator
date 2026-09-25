import base64
from collections import Counter
import io
import os
import random
import re
import shutil
import time
import urllib.parse
from janome.tokenizer import Tokenizer
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
import streamlit as st

# -------------------------------------------------------------
# 1. 画面デザイン・タイトルの設定
# -------------------------------------------------------------
st.set_page_config(
    page_title="うつログ称号ジェネレーター",
    page_icon="❄️",
    layout="centered",
)


# -------------------------------------------------------------
# ★ 日本語フォント取得関数
# -------------------------------------------------------------
def get_japanese_font():
    font_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/ipafont-gothic/ipag.ttf",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "NotoSansJP-Bold.ttf",
        "C:\\Windows\\Fonts\\meiryo.ttc",
    ]

    for path in font_candidates:
        if os.path.exists(path):
            return path

    return None


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

    /* 上の黒ウィンドウ枠 */
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
        color: #f1f5f9 !important;
        font-size: 0.95rem !important;
        line-height: 1.7 !important;
        margin-bottom: 0.8rem !important;
    }}

    .header-box .notice-text {{
        color: #cbd5e1 !important;
        font-size: 0.85rem !important;
        line-height: 1.5 !important;
        border-top: 1px solid #334155 !important;
        padding-top: 0.8rem !important;
        margin-top: 0.8rem !important;
    }}

    /* 下のフォーム枠（白背景固定） */
    div[data-testid="stTextInput"], div[data-testid="stRadio"], div[data-testid="stButton"] {{
        background-color: rgba(255, 255, 255, 0.92) !important;
        padding: 1rem !important;
        border-radius: 12px !important;
        margin-bottom: 1rem !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1) !important;
    }}

    /* フォーム枠内文字色（黒・ネイビー固定） */
    div[data-testid="stTextInput"] label, 
    div[data-testid="stRadio"] label, 
    div[data-testid="stRadio"] p,
    div[role="radiogroup"] label span {{
        color: #0f172a !important;
        font-weight: 600 !important;
    }}

    div[data-testid="stTextInput"] input {{
        color: #0f172a !important;
        background-color: #ffffff !important;
    }}

    div[data-testid="stTextInput"] input::placeholder {{
        color: #64748b !important;
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
        <h1>❄️ うつログ称号ジェネレーター 🖋️</h1>
        <p>@から始まる投稿者名を入力してボタンを押すと、過去コメントの言葉の傾向を解析して<br>「称号」を自動生成します、どんな称号が飛び出すかな？</p>
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
# 3. 称号生成関数（配信固有ワード追加＆絵文字除外フィルター搭載）
# -------------------------------------------------------------
def generate_nickname(comments):
    tokenizer = Tokenizer()
    words = []

    # ★ 優先度順のカスタム名詞（長い語や「様」「ミニ」等のパーツを含む単語を先頭に配置）
    custom_keywords = [
        "ミニうつろ",
        "ねろんが様",
        "ねろんが",
        "星めぐり学園",
        "11月15日",
        "ラルフさん",
        "美樹原",
        "お姉ちゃん",
        "姉ちゃん",
        "ワビスケ",
        "侘助",
        "鬼武者",
        "一閃",
        "リアイベ",
        "オフイベ",
        "カス姉",
        "涅槃",
        "CCJP",
        "KONAMI",
        "コナミ",
        "CAPCOM",
        "カプコン",
        "案件",
        "DbD",
        "歌枠",
        "シレン",
        "超神髄",
        "誕生日",
        "グッズ",
        "AC",
    ]

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

    # ★ 絵文字・特殊記号を除外する正規表現パターン
    emoji_pattern = re.compile(
        "["
        "\U0001f300-\U0001f9ff"  # 記号・絵文字
        "\U0001fa00-\U0001fa9f"
        "\u2600-\u27bf"  # 雑記号・絵文字（❄️, 🖋️, 🐸等）
        "\ufe0f"  # 異体字セレクタ
        "\u2744"  # ❄︎ (SNOWFLAKE)
        "]+",
        flags=re.UNICODE,
    )

    for comment in comments:
        # 絵文字や異体字記号を消去
        working_comment = emoji_pattern.sub("", comment)

        # 1. カスタム名詞の保護抽出（長い順・優先順にチェック）
        for ck in custom_keywords:
            if ck in working_comment:
                count_ck = working_comment.count(ck)
                # 「姉ちゃん」単体は「お姉ちゃん」に統一
                target_word = "お姉ちゃん" if ck == "姉ちゃん" else ck
                for _ in range(count_ck):
                    words.append(target_word)
                working_comment = working_comment.replace(ck, "")

        # 2. 通常の形態素解析
        for token in tokenizer.tokenize(working_comment):
            pos_details = token.part_of_speech.split(",")
            pos_main = pos_details[0]
            pos_sub = pos_details[1]

            if pos_main == "名詞":
                if pos_sub in allowed_subcategories or pos_sub == "*":
                    word = token.base_form
                    # 絵文字・1文字・除外ワードのチェック
                    if (
                        len(word) > 1
                        and word not in stop_words
                        and not emoji_pattern.search(word)
                    ):
                        words.append(word)
            elif pos_main == "カスタム名詞" or pos_main == "未知語":
                word = token.surface
                if (
                    len(word) > 1
                    and word not in stop_words
                    and not emoji_pattern.search(word)
                ):
                    words.append(word)

    word_counts = Counter(words)
    top_words = word_counts.most_common(5)

    if not top_words:
        return "【静寂を愛する雪原の通行人】", top_words

    # 同率1位の判定処理
    max_count = top_words[0][1]
    top_tier_words = [word for word, count in top_words if count == max_count]

    # 同率1位が3つ以上の場合の限定称号
    if len(top_tier_words) >= 3:
        t1, t2, t3 = (
            top_tier_words[0],
            top_tier_words[1],
            top_tier_words[2],
        )
        special_templates = [
            f"【{t1}と{t2}と{t3}が織りなす百花繚乱の語り部】",
            f"【{t1}・{t2}・{t3}を統べし三位一体の絶対者】",
            f"【{t1}・{t2}・{t3}が咲き乱れる言葉の絢爛】",
            f"【{t1}も{t2}も{t3}も愛する万能の雪原知識人】",
        ]
        return random.choice(special_templates), top_words

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
            f"【氷の結晶が導く{top1}と{top2}の全知全能の超越者】",
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
# ★ テーマ別名刺画像生成関数
# -------------------------------------------------------------
def create_card_image(author_name, title, top_words, theme="スノー・パステル"):
    width, height = 1000, 560

    specific_bg_file = None
    if theme == "スタイリッシュ・ダーク" and os.path.exists("bg_dark.png"):
        specific_bg_file = "bg_dark.png"
    elif theme == "プレミアム・ゴールド" and os.path.exists("bg_gold.png"):
        specific_bg_file = "bg_gold.png"
    elif theme == "スノー・パステル" and os.path.exists("bg_snow.png"):
        specific_bg_file = "bg_snow.png"
    elif os.path.exists("bg.png"):
        specific_bg_file = "bg.png"
    elif os.path.exists("bg.jpg"):
        specific_bg_file = "bg.jpg"

    if theme == "スタイリッシュ・ダーク":
        overlay_color = (15, 23, 42, 220)
        border_outer = (51, 65, 85)
        border_inner = (148, 163, 184)
        title_box_bg = (30, 41, 59)
        title_box_border = (51, 65, 85)
        text_dark = (248, 250, 252)
        text_sub = (148, 163, 184)
        red_accent = (244, 63, 94)
    elif theme == "プレミアム・ゴールド":
        overlay_color = (20, 20, 25, 210)
        border_outer = (217, 119, 6)
        border_inner = (251, 191, 36)
        title_box_bg = (35, 30, 20)
        title_box_border = (217, 119, 6)
        text_dark = (254, 243, 199)
        text_sub = (217, 119, 6)
        red_accent = (251, 191, 36)
    else:
        overlay_color = (255, 255, 255, 160)
        border_outer = (30, 41, 59)
        border_inner = (71, 85, 105)
        title_box_bg = (255, 255, 255)
        title_box_border = (226, 232, 240)
        text_dark = (15, 23, 42)
        text_sub = (51, 65, 85)
        red_accent = (225, 29, 72)

    if specific_bg_file:
        img = Image.open(specific_bg_file).convert("RGB")
        img = img.resize((width, height))
    else:
        img = Image.new("RGB", (width, height), color=(240, 248, 255))

    overlay = Image.new("RGBA", (width, height), overlay_color)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    draw.rectangle(
        [20, 20, width - 20, height - 20], outline=border_outer, width=3
    )
    draw.rectangle(
        [26, 26, width - 26, height - 26], outline=border_inner, width=1
    )

    font_path = get_japanese_font()

    if font_path:
        font_header = ImageFont.truetype(font_path, 22)
        font_author = ImageFont.truetype(font_path, 32)
        font_title = ImageFont.truetype(font_path, 30)
        font_rank_head = ImageFont.truetype(font_path, 24)
        font_rank_item = ImageFont.truetype(font_path, 22)
        font_footer = ImageFont.truetype(font_path, 18)
    else:
        font_header = font_author = font_title = font_rank_head = (
            font_rank_item
        ) = font_footer = ImageFont.load_default()

    draw.text(
        (50, 45), "うつログ称号ジェネレーター", fill=text_sub, font=font_header
    )
    draw.text((50, 85), f"投稿者: {author_name}", fill=text_dark, font=font_author)

    draw.rectangle(
        [50, 145, width - 50, 235],
        fill=title_box_bg,
        outline=title_box_border,
        width=2,
    )
    draw.text((70, 170), title, fill=red_accent, font=font_title)

    draw.text(
        (50, 265),
        "◇ 特徴的な名詞ランキング",
        fill=text_dark,
        font=font_rank_head,
    )

    y_pos = 310
    current_rank = 1
    for idx, (word, count) in enumerate(top_words[:3]):
        if idx > 0 and count == top_words[idx - 1][1]:
            rank_str = f"第 {current_rank} 位(同率)"
        else:
            current_rank = idx + 1
            rank_str = f"第 {current_rank} 位"

        draw.text(
            (70, y_pos),
            f"{rank_str}:   {word}   ({count} 回)",
            fill=text_dark,
            font=font_rank_item,
        )
        y_pos += 42

    draw.text(
        (50, 490),
        "#うつログ称号ジェネレーター  |  氷室うつろ非公式ファンツール",
        fill=text_sub,
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
        "称号を獲得する！", type="primary", use_container_width=True
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
            st.session_state["comments"] = comments
            st.session_state["target_author"] = target_author
            title, top_words = generate_nickname(comments)
            st.session_state["title"] = title
            st.session_state["top_words"] = top_words
        else:
            st.error(
                "コメントが取得できませんでした。投稿者名を確認してください。"
            )
    else:
        st.warning("投稿者名を入力してね！")

# -------------------------------------------------------------
# ★ 結果表示＆名刺テーマ切り替えエリア
# -------------------------------------------------------------
if "title" in st.session_state:
    target_author = st.session_state["target_author"]
    title = st.session_state["title"]
    top_words = st.session_state["top_words"]

    st.success("解析完了！")

    st.markdown("---")
    st.subheader(f"🏷️ `{target_author}` の獲得称号")
    st.header(f":red[{title}]")
    st.markdown("---")

    st.subheader("❄️ 特徴的な名詞ランキング 🖋️（Top 5）")

    current_rank = 1
    for idx, (word, count) in enumerate(top_words, 0):
        if idx > 0 and count == top_words[idx - 1][1]:
            rank_label = f"👑 第 {current_rank} 位 (同率)"
        else:
            current_rank = idx + 1
            rank_label = f"第 {current_rank} 位"

        st.write(f"**{rank_label}**: `{word}` （{count} 回出現）")

    st.markdown("---")

    st.subheader("🎴 獲得称号名刺")

    selected_theme = st.radio(
        "名刺カードのデザインテーマを選択してください",
        options=[
            "❄️ スノー・パステル",
            "🌑 スタイリッシュ・ダーク",
            "✨ プレミアム・ゴールド",
        ],
        index=0,
        horizontal=True,
    )

    theme_name = selected_theme.split(" ")[1]

    img_bytes = create_card_image(
        target_author, title, top_words, theme=theme_name
    )

    st.image(
        img_bytes, caption=f"称号名刺カード（{selected_theme}）", use_container_width=True
    )

    st.write("")

    btn_col1, btn_col2 = st.columns([1, 1])

    with btn_col1:
        st.download_button(
            label="💾 選択した名刺画像を保存する",
            data=img_bytes,
            file_name=f"utsulog_card_{target_author}.png",
            mime="image/png",
            use_container_width=True,
        )

    with btn_col2:
        app_url = "https://utsulog-title-generator.streamlit.app"
        try:
            if hasattr(st, "context") and hasattr(st.context, "headers"):
                host = st.context.headers.get("host", "")
                if host:
                    app_url = f"https://{host}"
        except Exception:
            pass

        raw_tweet_text = (
            f"{target_author} の獲得称号は…\n\n"
            f"✨ {title} ✨\n\n"
            f"👇 うつログ称号ジェネレーターはこちら！\n"
            f"{app_url}\n\n"
            f"#うつログ称号ジェネレーター #氷室うつろ"
        )
        encoded_text = urllib.parse.quote(raw_tweet_text)
        tweet_url = f"https://x.com/intent/post?text={encoded_text}"

        st.markdown(
            f'<a href="{tweet_url}" target="_blank" class="x-share-btn" style="width: 100%; display: block; text-align: center;">𝕏 に称号をポストする</a>',
            unsafe_allow_html=True,
        )
