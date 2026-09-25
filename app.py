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

            # ★ 修正ポイント1: 検索後の初回データ読み込みを確実に待つ
            page.wait_for_selector("p.text-slate-700", timeout=5000)
            time.sleep(1.0)  # 初回描画待ちを0.5秒長く確保
        except Exception:
            # タイムアウトした場合も少し待ってみる
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

            # ★ 修正ポイント2: まだ1件も取れていない時はスクロールせずに少し待つ
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
