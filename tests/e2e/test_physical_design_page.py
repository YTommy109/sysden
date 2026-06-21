"""GET /tables/{name}/physical — 物理設計ページの E2E テスト。"""

import re
from collections.abc import Callable

from playwright.sync_api import Page, expect


def test_物理設計ページへの遷移(
    page: Page, base_url: str, create_table: Callable[..., None]
) -> None:
    # Given: テーブルが存在する状態でテーブル詳細ページにアクセス
    create_table("users")
    page.goto(f"{base_url}/tables/users")

    # When: 物理設計リンクをクリックする
    page.get_by_role("link", name="物理設計").click()

    # Then: 物理設計ページが表示される
    expect(page).to_have_url(re.compile(r"/tables/\w+/physical"))
    expect(page.locator("h1")).to_contain_text("物理設計")


def test_物理設計の未生成状態(page: Page, base_url: str, create_table: Callable[..., None]) -> None:
    # Given: テーブルの物理設計ページにアクセス
    create_table("users")
    page.goto(f"{base_url}/tables/users/physical")

    # Then: 未生成メッセージと生成ボタンが表示される
    expect(page.get_by_text("まだ物理設計がありません")).to_be_visible()
    expect(page.get_by_role("button", name=re.compile("物理設計を生成"))).to_be_visible()


def test_物理設計の生成ボタンで生成される(
    page: Page, base_url: str, create_table: Callable[..., None]
) -> None:
    # Given: テーブルの物理設計ページで未生成状態
    create_table("users")
    page.goto(f"{base_url}/tables/users/physical")

    # When: 生成ボタンをクリックする
    page.get_by_role("button", name=re.compile("物理設計を生成")).click()

    # Then: 物理設計の内容が表示される（スタブの内容）
    page.wait_for_url(re.compile(r"/tables/\w+/physical"))
    expect(page.get_by_text("まだ物理設計がありません")).not_to_be_visible()


def test_物理設計ページから論理設計に戻れる(
    page: Page, base_url: str, create_table: Callable[..., None]
) -> None:
    # Given: 物理設計ページにいる
    create_table("users")
    page.goto(f"{base_url}/tables/users/physical")

    # When: 戻るリンクをクリックする
    page.get_by_role("link", name="論理設計に戻る").click()

    # Then: 論理設計ページに遷移する
    expect(page).to_have_url(re.compile(r"/tables/\w+$"))
