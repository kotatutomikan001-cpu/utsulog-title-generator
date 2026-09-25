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

    .reason-tag {{
        font-size: 0.82rem;
        color: #d97706;
        background-color: #fef3c7;
        padding: 2px 6px;
        border-radius: 4px;
        margin-left: 6px;
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
# 3. 称号生成関数（同率不採用理由の解析・出力対応）
# -------------------------------------------------------------
def generate_nickname(comments):
    tokenizer = Tokenizer()
    words = []
    first_seen = {}  # 各単語の初出インデックス保持用

    custom_keywords = [
        "スパチュンパートナーズ",
        "スパチュンパートナー",
        "ゴッドハンド",
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
        "毒チワワ",
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
        "…",
        "...",
        "..",
        "‥",
        "―",
        "〜",
        "～",
    }

    allowed_subcategories = [
        "一般",
        "固有名詞",
        "サ変接続",
        "形容動詞語幹",
        "ナイ形容詞語幹",
    ]

    symbol_pattern = re.compile(
        "["
        "\U0001f300-\U0001f9ff"
        "\U0001fa00-\U0001fa9f"
        "\u2600-\u27bf"
        "\ufe0f"
        "\u2744"
        "…‥・―～〜!！?？♪★☆◇◆◎○●"
        "]+",
        flags=re.UNICODE,
    )

    for idx, comment in enumerate(comments):
        working_comment = symbol_pattern.sub(" ", comment)

        # 1. カスタム名詞の保護抽出
        for ck in custom_keywords:
            if ck in working_comment:
                count_ck = working_comment.count(ck)
                target_word = (
                    "お姉ちゃん"
                    if ck == "姉ちゃん"
                    else (
                        "スパチュンパートナーズ"
                        if ck == "スパチュンパートナー"
                        else ck
                    )
                )

                for _ in range(count_ck):
                    words.append(target_word)
                    if target_word not in first_seen:
                        first_seen[target_word] = idx
                working_comment = working_comment.replace(ck, " ")

        # 2. 通常の形態素解析
        for token in tokenizer.tokenize(working_comment):
            pos_details = token.part_of_speech.split(",")
            pos_main = pos_details[0]
            pos_sub = pos_details[1]

            if pos_main == "名詞" and pos_sub != "数":
                if pos_sub in allowed_subcategories or pos_sub == "*":
                    word = token.base_form.strip()
                    if (
                        len(word) > 1
                        and word not in stop_words
                        and not symbol_pattern.search(word)
                        and not re.match(r"^[\.\…\―\─\～\〜]+$", word)
                    ):
                        words.append(word)
                        if word not in first_seen:
                            first_seen[word] = idx
            elif pos_main in ["カスタム名詞", "未知語"]:
                word = token.surface.strip()
                if (
                    len(word) > 1
                    and word not in stop_words
                    and not symbol_pattern.search(word)
                    and not re.match(r"^[\.\…\―\─\～\〜]+$", word)
                ):
                    words.append(word)
                    if word not in first_seen:
                        first_seen[word] = idx

    word_counts = Counter(words)
    top_words_raw = word_counts.most_common(10)

    if not top_words_raw:
        return "【静寂を愛する雪原の通行人】", [], {}

    # ★ 同率時の採用優先順位決定（①回数 > ②文字数長 > ③初出順 > ④五十音順）
    sorted_words = sorted(
        top_words_raw,
        key=lambda x: (
            x[1],
            len(x[0]),
            -first_seen.get(x[0], 99999),
            x[0],
        ),
        reverse=True,
    )

    top_words = sorted_words[:5]

    # ★ 同率理由の解析マッピング構築
    reasons = {}
    max_count = top_words[0][1]
    top_tier_words = [w for w, c in top_words if c == max_count]

    is_special_three = len(top_tier_words) >= 3

    for i, (word, count) in enumerate(top_words):
        # 他に同じ出現回数の単語が存在するか確認
        same_count_group = [w for w, c in top_words if c == count]

        if len(same_count_group) > 1:
            if is_special_three and count == max_count and i < 3:
                reasons[word] = "🌟 限定称号にトリプル採用！"
            elif i == 0 or (i == 1 and not is_special_three):
                reasons[word] = "✨ 称号メインキーワードに選出！"
            else:
                # 選ばれなかった理由の具体判定
                winner = top_words[0][0]
                if len(word) < len(winner):
                    reasons[word] = (
                        f"💡 同率{count}回：文字数が短い（{winner}を優先）"
                    )
                elif first_seen.get(word, 0) > first_seen.get(winner, 0):
                    reasons[word] = (
                        f"💡 同率{count}回：コメント初出順（{winner}が先出）"
                    )
                else:
                    reasons[word] = (
                        f"💡 同率{count}回：五十音順（{winner}を優先）"
                    )
        else:
            reasons[word] = ""

    # 称号決定ロジック
    if is_special_three:
        t1, t2, t3 = (
            top_tier_words[0],
            top_tier_words[1],
            top_tier_words[2],
        )
        special_templates = [
            f"【{t1}と{t2}と{t3}を語り継ぐ百花繚乱の語り部】",
            f"【{t1}・{t2}・{t3}を統べし三位一体の絶対者】",
            f"【{t1}・{t2}・{t3}の言葉を極めし賢者】",
            f"【{t1}も{t2}も{t3}も愛する万能の雪原知識人】",
        ]
        return random.choice(special_templates), top_words, reasons

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
            f"【氷室の深淵にて{top1}と{top2}を極めし探求者】",
            f"【白銀の領域を統べる{top1}と{top2}の主】",
        ]
    elif count1 >= 15:
        templates = [
            f"【凍てつく夜に輝く{top1}と{top2}の探求者】",
            f"【うつろの雪原を拓く{top1}と{top2}のマスター】",
            f"【星めぐりの学園で{top1}と{top2}を語る伝道者】",
            f"【静寂の氷晶に{top1}と{top2}を紡ぐ職人】",
        ]
    else:
        templates = [
            f"【うつろの雪原に舞い降りし{top1}と{top2}の新星】",
            f"【粉雪とともに{top1}と{top2}を愛でる者】",
            f"【ひんやり優しく{top1}と{top2}を語る者】",
            f"【氷室の風に乗せて{top1}と{top2}を届ける案内人】",
        ]

    selected_title = random.choice(templates)
    return selected_title, top_words, reasons


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
            title, top_words, reasons = generate_nickname(comments)
            st.session_state["title"] = title
            st.session_state["top_words"] = top_words
            st.session_state["reasons"] = reasons
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
    reasons = st.session_state.get("reasons", {})

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

        reason_text = reasons.get(word, "")
        reason_html = (
            f'<span class="reason-tag">{reason_text}</span>'
            if reason_text
            else ""
        )

        st.markdown(
            f"**{rank_label}**: `{word}` （{count} 回出現） {reason_html}",
            unsafe_allow_html=True,
        )

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
