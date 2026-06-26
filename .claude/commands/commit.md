# /commit — コミット提案

**必ず以下の順で現在の変更内容を調査してからメッセージを作成してください。会話履歴から変更内容を推測してはいけません。**

```bash
git status
git diff --staged
git diff
git log --oneline -5
```

[docs/coding_rule.md のコミット規約](../docs/coding_rule.md#コミット規約)に従ってメッセージを作成する。

メッセージを提案したら、確認後に `git commit -m "..."` を実行してください。
