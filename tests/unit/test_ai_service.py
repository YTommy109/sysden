from unittest.mock import MagicMock, patch

from app import ai_service


def test_generate_table_design_calls_openai() -> None:
    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    )
    with patch("app.ai_service.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response
        result = ai_service.generate_table_design("ユーザーテーブル")
    assert "column_name" in result
    assert "id" in result


def test_generate_table_design_includes_current_tsv() -> None:
    current = "column_name\ttype\n"
    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
    )
    captured: list[dict] = []

    def capture(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs)
        return mock_response

    with patch("app.ai_service.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.side_effect = capture
        ai_service.generate_table_design("カラムを追加", current)

    msgs = captured[0]["messages"]
    assert any("現在のテーブル定義" in m["content"] for m in msgs)
