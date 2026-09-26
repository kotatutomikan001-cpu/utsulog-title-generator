import base64
from collections import Counter
import io
import os
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
    page_title="うつログ（うつろ書架）の称号診断",
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

    /* 上の黒ウィンドウ枠（常に白文字固定） */
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
        line-height: 1.4 !important;
    }}

    /* ルビ（ふりがな）用スタイリング */
    .header-box ruby {{
        ruby-align: center;
    }}
    
    .header-box rt {{
        font-size: 0.55em !important;
        color: #94a3b8 !important;
        font-weight: normal !important;
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
        <h1>❄️ <ruby>うつろ書架<rt>うつログ</rt></ruby>の称号診断 🖋️</h1>
        <p>@から始まる投稿者名を入力してボタンを押すと、うつログを介して過去に”Utsuro CH. 氷室うつろ”で発言したコメントの傾向を解析して「称号」を自動生成します。<br>果たしてどんな称号が誕生してしまうのか・・・</p>
        <div class="notice-text">
            ※検索機能をお借りしているうつログのサーバー負荷軽減および処理時間短縮のため、解析件数を選択できるようにしています。（仕様上、過去コメントは最大3000件まで遡ることができます）<br>
            ※過去コメントのデータ取得処理はクラウドサーバー上で行われるため、スマホの通信量（ギガ）消費はごくわずか（1回あたり数MB程度）です。安心してご利用ください。
        </div>
    </div>
""",
    unsafe_allow_html=True,
)


# -------------------------------------------------------------
# 2. コメント取得関数（起動直後の読み込み安定化版）
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

            # 初回アクセス時の要素レンダリング完了を最大5秒待機
            page.wait_for_selector("p.text-slate-700", timeout=5000)
            time.sleep(1.0)
        except Exception:
            time.sleep(2.0)

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
                time.sleep(1.0)
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
# 3. 称号生成関数
# -------------------------------------------------------------
def generate_nickname(comments):
    tokenizer = Tokenizer()
    words = []

    custom_keywords = [
        "シュウォッチ",
        "連打測定",
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
        "連射",
        "連打",
        "AC",
    ]

    stop_words = {
        "流石",
        "さすが",
        "すか",
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

    for comment in comments:
        working_comment = symbol_pattern.sub(" ", comment)

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
                working_comment = working_comment.replace(ck, " ")

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
            elif pos_main in ["カスタム名詞", "未知語"]:
                word = token.surface.strip()
                if (
                    len(word) > 1
                    and word not in stop_words
                    and not symbol_pattern.search(word)
                    and not re.match(r"^[\.\…\―\─\～\〜]+$", word)
                ):
                    words.append(word)

    word_counts = Counter(words)
    top_words = word_counts.most_common(5)

    if not top_words:
        return "【静寂を愛する白銀の図書委員】", top_words

    total_count_sum = sum([count for word, count in top_words])
    primary_word_code = sum([ord(c) for c in top_words[0][0]])
    hash_value = total_count_sum + primary_word_code

    max_count = top_words[0][1]
    top_tier_words = [word for word, count in top_words if count == max_count]

    if len(top_tier_words) >= 3:
        t1, t2, t3 = (
            top_tier_words[0],
            top_tier_words[1],
            top_tier_words[2],
        )
        special_templates = [
            f"【{t1}を白銀に刻み{t2}と{t3}を誌面に記す編纂者】",
            f"【{t1}を司り{t2}を解き明かし{t3}の言葉を極めし賢者】",
            f"【{t1}の羊皮紙を紐解き{t2}と{t3}の真理を紡ぐ語り部】",
            f"【{t1}の筆跡に{t2}を重ね{t3}の領域を統べる絶対者】",
            f"【{t1}を胸に{t2}の詩編を詠み{t3}を愛でる雪原知識人】",
            f"【{t1}の書庫から{t2}を取り出し{t3}の未来を描く創世主】",
            f"【{t1}を誌面に讃え{t2}と{t3}の旋律を奏でる超越者】",
            f"【{t1}のペンを握り{t2}の深淵と{t3}の極致へ挑む探求者】",
            f"【{t1}を記しし原稿に{t2}と{t3}の軌跡を残す職人】",
            f"【{t1}の書巻を広げ{t2}を認め{t3}を語り継ぐマスター】",
        ]
        selected_idx = hash_value % len(special_templates)
        return special_templates[selected_idx], top_words

    top1, count1 = top_words[0]
    top2 = (
        top_words[1][0]
        if len(top_words) > 1
        else ("言葉" if top1 != "言葉" else "話題")
    )

    if count1 >= 40:
        templates = [
            f"【{top1}の白銀図書館で{top2}の真理を刻みし絶対神】",
            f"【{top1}を司る万年筆で{top2}の創世記を編む創世主】",
            f"【{top1}の書架を紐解き{top2}の極致を記す支配者】",
            f"【{top1}を氷晶のペンに込め{top2}の未来へ導く超越者】",
            f"【{top1}の深淵を統べし者にして{top2}を詩う絶対者】",
            f"【{top1}の羊皮紙を刻み{top2}の大体系を創出せし神】",
            f"【{top1}を筆先から放ち{top2}の世界を創造せし創世主】",
            f"【{top1}の大百科を著し{top2}の真理を掲げる支配者】",
            f"【{top1}のインクで歴史を染め{top2}の運命を執筆せし絶対神】",
            f"【{top1}の全書庫を制し{top2}の真髄に到達せし超越者】",
        ]
    elif count1 >= 25:
        templates = [
            f"【{top1}を白銀に刻み{top2}の物語を認める覇王】",
            f"【{top1}の空に想いを馳せ{top2}の章を詠む英雄】",
            f"【{top1}の書庫に深く潜り{top2}の真理を極めし執筆者】",
            f"【{top1}の書巻を広げ{top2}の領域を統べる主】",
            f"【{top1}を凍てつく筆下に込め{top2}を描く者】",
            f"【{top1}の図書室で静かに{top2}の解を導く英雄】",
            f"【{top1}を原稿用紙に走らせ{top2}を解き明かす覇王】",
            f"【{top1}を万年筆に宿し{top2}の歴史を紡ぐ主】",
            f"【{top1}に栞を挟み{top2}の魅力を熱く語る探求者】",
            f"【{top1}の美しい筆致で{top2}の誌面を彩る覇王】",
        ]
    elif count1 >= 10:
        templates = [
            f"【{top1}のインクを紡ぎ{top2}の軌跡を記す探求者】",
            f"【{top1}のノートを開き{top2}の世界を拓くマスター】",
            f"【{top1}を愛する文豪として{top2}の物語を綴る伝道者】",
            f"【{top1}の氷晶を抱き{top2}の篇章を認める職人】",
            f"【{top1}の原稿用紙に{top2}の想いを走らせるマスター】",
            f"【{top1}の書簡をしたため{top2}への愛を語る編纂者】",
            f"【{top1}を冴えた筆先で捉え{top2}の詩を認める探求者】",
            f"【{top1}の静寂の中で{top2}の旋律を紡ぐ職人】",
            f"【{top1}の書架から紐解き{top2}を語り継ぐ伝道者】",
            f"【{top1}をインク瓶から掬い{top2}の言葉へ昇華させるマスター】",
        ]
    else:
        templates = [
            f"【{top1}のキャンバスに{top2}の記憶を書き留める新星】",
            f"【{top1}を雪の羽ペンに載せ{top2}を優しく綴る者】",
            f"【{top1}のぬくもりを胸に{top2}を誌面に描く者】",
            f"【{top1}の風に乗り{top2}の書簡を届ける案内人】",
            f"【{top1}の傍らにペンを置き{top2}を愛でる案内人】",
            f"【{top1}のメモ帳を開き{top2}を小さく認める新星】",
            f"【{top1}をノートの片隅に記し{top2}を描く者】",
            f"【{top1}の書架の前で静かに{top2}を語る愛好家】",
            f"【{top1}の便せんを広げ{top2}の手紙をしたためる者】",
            f"【{top1}を氷の結晶のペンで{top2}の横にそっと記す新星】",
        ]

    selected_idx = hash_value % len(templates)
    selected_title = templates[selected_idx]

    return selected_title, top_words


# -------------------------------------------------------------
# ★ 縁取り文字描画用ヘルパー関数
# -------------------------------------------------------------
def draw_text_with_outline(
    draw,
    position,
    text,
    font,
    fill_color,
    outline_color=None,
    outline_range=0,
):
    x, y = position
    if outline_range > 0 and outline_color:
        for dx in range(-outline_range, outline_range + 1):
            for dy in range(-outline_range, outline_range + 1):
                if dx != 0 or dy != 0:
                    draw.text(
                        (x + dx, y + dy), text, font=font, fill=outline_color
                    )
    draw.text((x, y), text, font=font, fill=fill_color)


# -------------------------------------------------------------
# ★ テーマ別名刺画像生成関数（「おまさい」称号背景透過版）
# -------------------------------------------------------------
def create_card_image(author_name, title, top_words, theme="おまさい"):
    width, height = 1000, 560

    specific_bg_file = None

    if theme == "おまさい":
        candidates = ["bg_omasai.png", "bg_0.png", "bg.png", "bg.jpg"]
    elif theme == "うつろ①":
        candidates = ["bg_utsuro1.png", "bg_1.png", "bg_1.jpg"]
    elif theme == "うつろ②":
        candidates = ["bg_utsuro2.png", "bg_2.png", "bg_2.jpg"]
    elif theme == "うつろ③":
        candidates = ["bg_utsuro3.png", "bg_3.png", "bg_3.jpg"]
    elif theme == "うつろ④":
        candidates = ["bg_utsuro4.png", "bg_4.png", "bg_4.jpg"]
    elif theme == "うつろ⑤":
        candidates = ["bg_utsuro5.png", "bg_5.png", "bg_5.jpg"]
    else:
        candidates = ["bg.png", "bg.jpg"]

    for cand in candidates:
        if os.path.exists(cand):
            specific_bg_file = cand
            break

    if specific_bg_file:
        img = Image.open(specific_bg_file).convert("RGBA")
        img = img.resize((width, height))
    else:
        img = Image.new("RGBA", (width, height), color=(240, 248, 255, 255))

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if theme == "おまさい":
        card_base_bg = Image.new("RGBA", (width, height), (255, 255, 255, 160))
        img = Image.alpha_composite(img, card_base_bg)

        border_outer = (51, 65, 85, 220)
        border_inner = (148, 163, 184, 220)

        # 薄い水色のまま透過処理（アルファ値 230 → 140）
        title_box_bg = (224, 242, 254, 140)
        title_box_border = (186, 230, 253, 200)

        text_dark = (15, 23, 42)
        text_sub = (71, 85, 105)
        red_accent = (244, 63, 94)
        outline_c = None
        outline_r = 0
    else:
        card_base_bg = Image.new("RGBA", (width, height), (255, 255, 255, 120))
        img = Image.alpha_composite(img, card_base_bg)

        border_outer = (51, 65, 85, 200)
        border_inner = (148, 163, 184, 200)

        title_box_bg = (255, 255, 255, 210)
        title_box_border = (203, 213, 225, 220)

        text_dark = (15, 23, 42)
        text_sub = (51, 65, 85)
        red_accent = (225, 29, 72)
        outline_c = (255, 255, 255)
        outline_r = 2

    draw.rectangle(
        [20, 20, width - 20, height - 20], outline=border_outer, width=3
    )
    draw.rectangle(
        [26, 26, width - 26, height - 26], outline=border_inner, width=1
    )

    font_path = get_japanese_font()

    if font_path:
        font_ruby = ImageFont.truetype(font_path, 13)
        font_header = ImageFont.truetype(font_path, 22)
        font_author = ImageFont.truetype(font_path, 32)
        font_rank_head = ImageFont.truetype(font_path, 24)
        font_rank_item = ImageFont.truetype(font_path, 22)
        font_footer = ImageFont.truetype(font_path, 18)
    else:
        font_ruby = font_header = font_author = font_rank_head = (
            font_rank_item
        ) = font_footer = ImageFont.load_default()

    # 1. ヘッダー
    draw_text_with_outline(
        draw,
        (85, 28),
        "うつログ",
        font_ruby,
        text_sub,
        outline_color=outline_c,
        outline_range=outline_r,
    )

    draw_text_with_outline(
        draw,
        (50, 45),
        "うつろ書架の称号診断",
        font_header,
        text_sub,
        outline_color=outline_c,
        outline_range=outline_r,
    )

    # 2. 投稿者名
    draw_text_with_outline(
        draw,
        (50, 85),
        f"投稿者: {author_name}",
        font_author,
        text_dark,
        outline_color=outline_c,
        outline_range=outline_r,
    )

    # 3. 称号枠の描画
    draw.rectangle(
        [50, 145, width - 50, 235],
        fill=title_box_bg,
        outline=title_box_border,
        width=2,
    )

    # 称号の1行収容＆中央寄せ（センタリング）計算
    max_title_width = (width - 50) - 70 - 20  # 860px
    target_font_size = 30
    final_text_w = 0

    if font_path:
        while target_font_size >= 12:
            test_font = ImageFont.truetype(font_path, target_font_size)
            try:
                bbox = test_font.getbbox(title)
                text_w = bbox[2] - bbox[0]
            except Exception:
                text_w = target_font_size * len(title)

            if text_w <= max_title_width:
                font_title = test_font
                final_text_w = text_w
                break
            target_font_size -= 1
        else:
            font_title = ImageFont.truetype(font_path, 12)
            final_text_w = max_title_width
    else:
        font_title = ImageFont.load_default()
        final_text_w = target_font_size * len(title)

    title_x = int((width - final_text_w) / 2)
    title_y = 170 + int((30 - target_font_size) * 0.45)

    title_text_color = red_accent
    draw_text_with_outline(
        draw,
        (title_x, title_y),
        title,
        font_title,
        title_text_color,
        outline_range=0,
    )

    # 4. ランキング見出し
    draw_text_with_outline(
        draw,
        (50, 265),
        "◇ 特徴的な名詞ランキング",
        font_rank_head,
        text_dark,
        outline_color=outline_c,
        outline_range=outline_r,
    )

    # 5. ランキング項目
    y_pos = 310
    current_rank = 1
    for idx, (word, count) in enumerate(top_words[:3]):
        if idx > 0 and count == top_words[idx - 1][1]:
            rank_str = f"第 {current_rank} 位(同率)"
        else:
            current_rank = idx + 1
            rank_str = f"第 {current_rank} 位"

        draw_text_with_outline(
            draw,
            (70, y_pos),
            f"{rank_str}:   {word}   ({count} 回)",
            font_rank_item,
            text_dark,
            outline_color=outline_c,
            outline_range=outline_r,
        )
        y_pos += 42

    # 6. フッター
    draw_text_with_outline(
        draw,
        (50, 490),
        "#うつろ書架の称号診断  |  氷室うつろ非公式ファンツール",
        font_footer,
        text_sub,
        outline_color=outline_c,
        outline_range=0,
    )

    final_img = Image.alpha_composite(img, overlay).convert("RGB")

    buf = io.BytesIO()
    final_img.save(buf, format="PNG")
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

    # 称号が文字数に応じて自動的にフォントサイズ補正され、1行に収まるスタイリング
    title_len = max(len(title), 1)
    st.markdown(
        f"""
        <div style="
            text-align: center;
            font-size: min(1.8rem, calc(82vw / {title_len}));
            font-weight: bold;
            color: #e11d48;
            white-space: nowrap;
            overflow: visible;
            margin: 0.8rem 0;
            line-height: 1.2;
        ">
            {title}
        </div>
        """,
        unsafe_allow_html=True,
    )
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
            "おまさい",
            "うつろ①",
            "うつろ②",
            "うつろ③",
            "うつろ④",
            "うつろ⑤",
        ],
        index=0,
        horizontal=True,
    )

    img_bytes = create_card_image(
        target_author, title, top_words, theme=selected_theme
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
            file_name=f"utsulog_card_{target_author}_{selected_theme}.png",
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
            f"👇 うつろ書架（うつログ）の称号診断はこちら！\n"
            f"{app_url}\n\n"
            f"※保存した名刺画像を添えてポストしてね！\n"
            f"#うつろ書架の称号診断 #うつログ #氷室うつろ"
        )
        encoded_text = urllib.parse.quote(raw_tweet_text)
        tweet_url = f"https://x.com/intent/post?text={encoded_text}"

        st.markdown(
            f'<a href="{tweet_url}" target="_blank" class="x-share-btn" style="width: 100%; display: block; text-align: center;">𝕏 に称号をポストする</a>',
            unsafe_allow_html=True,
        )
