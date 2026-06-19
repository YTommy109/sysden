import os
from pathlib import Path


def get_data_dir() -> Path:
    """TSV ファイルの格納ディレクトリを返す。

    Returns:
        環境変数 ``SYSDEN_DATA`` のパス。未設定時は ``.data``。
    """
    return Path(os.environ.get("SYSDEN_DATA", ".data"))
