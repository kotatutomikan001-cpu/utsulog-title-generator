import io
import re
import streamlit as st
from janome.tokenizer import Tokenizer
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

# --------------------------------------------------
# 1. ページ設定
# --------------------------------------------------
st.set_page_config(
    page_title="うつログコメントからの二つ名自動生成",
    page_icon="❄️",
    layout="centered",
)

st.title("❄️ うつログ二つ名・称号ジェネレーター")
st.caption("YouTubeコメントなどから形態素解析で二つ名を自動生成するよ！")


# --------------------------------------------------
# 2. 縁取り付きテキスト描画関数（※ここがエラーの修正箇所！）
# --------------------------------------------------
def draw_text_with_outline(
    draw,
    position,
    text,
    font,
    text_color="white",
    outline_color="black",
    outline_width=2,
):
    """文字の周りに縁取り（アウトライン）をつけて描画する関数

    ※ 'outline_0' などの存在しない引数は使わず、正しいパラメータで描画するよ
    """
    x, y = position

    # 上下左右・斜めにずらして縁取りを描画
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0:
                draw.text(
                    (x + dx, y + dy), text, font=font, fill=outline_color
                )

    # 中央にメインの文字を描画
    draw.text((x, y), text, font=font, fill=text_color)


# --------------------------------------------------
# 3. カード画像生成処理
# --------------------------------------------------
def create_card_image(title_text, name_text="うつろスキー"):
    """二つ名・称号カードの画像を作成してバイナリ（BytesIO）で返す"""
    # 600x350 のベース画像を作成（紺色背景）
    width, height = 600, 350
    image = Image.new("RGB", (width, height), color=(20, 24, 38))
    draw = ImageDraw.Draw(image)

    # 枠線の描画
    draw.rectangle([10, 10, width - 10, height - 10], outline=(100, 180, 255), width=3)

    # フォントの読み込み（標準フォントを使用。必要に応じてパスを指定してね）
    try:
        title_font = ImageFont.truetype("arial.ttf", 36)
        name_font = ImageFont.truetype("arial.ttf", 24)
    except IOError:
        title_font = ImageFont.load_default()
        name_font = ImageFont.load_default()

    # 二つ名/称号テキストの描画（修正した描画関数を呼び出し）
    draw_text_with_outline(
        draw=draw,
        position=(40, 100),
        text=f"【{title_text}】",
        font=title_font,
        text_color="#FFFFFF",
        outline_color="#0055AA",
        outline_width=3,
    )

    # 名前の描画
    draw_text_with_outline(
        draw=draw,
        position=(40, 220),
        text=f"獲得者: {name_text}",
        font=name_font,
        text_color="#E0E0E0",
        outline_color="#111111",
        outline_width=2,
    )

    # 画像を BytesIO に保存して返却
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)
    return img_byte_arr


# --------------------------------------------------
# 4. 二つ名生成ロジック（Janome形態素解析）
# --------------------------------------------------
def generate_title_from_text(input_text):
    """入力テキストから名詞や形容詞を抽出して二つ名を組み合わせる"""
    tokenizer = Tokenizer()
    tokens = list(tokenizer.tokenize(input_text))

    nouns = [t.surface for t in tokens if t.part_of_speech.startswith("名詞")]
    adjectives = [
        t.surface for t in tokens if t.part_of_speech.startswith("形容詞")
    ]

    prefix = adjectives[0] if adjectives else "静かなる"
    suffix = nouns[0] if nouns else "観察者"

    if len(nouns) >= 2:
        prefix = nouns[0]
        suffix = nouns[1]

    return f"{prefix}の{suffix}"


# --------------------------------------------------
# 5. メイン画面（Streamlit UI）
# --------------------------------------------------
user_name = st.text_input("ユーザー名を入力", value="うつろスキー")
comment_text = st.text_area("二つ名の元になるコメントやテキスト", value="氷室うつろさんの配信はいつも楽しくて癒やされます！")

if st.button("二つ名を生成する！"):
    if comment_text.strip():
        # 1. 二つ名の生成
        title = generate_title_from_text(comment_text)
        st.success(f"生成された二つ名: **【{title}】**")

        # 2. カード画像の生成
        img_bytes = create_card_image(title_text=title, name_text=user_name)

        # 3. 画像の表示（※ Streamlitの最新仕様に合わせて width 調整）
        st.image(img_bytes, caption="生成された称号カード", width=500)

        # 4. ダウンロードボタン
        st.download_button(
            label="カード画像をダウンロード",
            data=img_bytes,
            file_name=f"title_card_{user_name}.png",
            mime="image/png",
        )
    else:
        st.warning("テキストを入力してね！")
