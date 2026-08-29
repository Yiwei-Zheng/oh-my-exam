from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SHARED_SRC = ROOT / "tools" / "shared" / "cie" / "src"
TOOL_SRC = ROOT / "tools" / "downloaders" / "alevel" / "cie" / "src"

if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))
if str(TOOL_SRC) not in sys.path:
    sys.path.insert(0, str(TOOL_SRC))


MESSAGES = {
    "zh": {
        "description": "同步 Cambridge 官方 AS/A Level 科目目录 / Sync Cambridge official AS & A Level subject catalog.",
        "output_dir": "输出目录 / output directory.",
        "no_overview": "只抓取科目列表，跳过每个科目的 overview 页面 / only fetch the subject list.",
        "delay": "访问每个科目页面后的等待秒数 / delay seconds after each subject page.",
        "lang": "界面语言 / language.",
        "subjects": "官方科目文件",
        "rules": "下载规则文件",
    },
    "en": {
        "description": "Sync Cambridge official AS & A Level subject catalog. / 同步 Cambridge 官方 AS/A Level 科目目录。",
        "output_dir": "Output directory. / 输出目录。",
        "no_overview": "Only fetch the subject list; skip per-subject overview pages. / 只抓取科目列表。",
        "delay": "Delay seconds after each subject page. / 访问每个科目页面后的等待秒数。",
        "lang": "Language. / 界面语言。",
        "subjects": "subjects",
        "rules": "rules",
    },
}


def main() -> None:
    from oh_my_exam.pipelines.adapters.cie_alevel.downloader.cambridge_catalog import sync_catalog

    parser = argparse.ArgumentParser(description=MESSAGES["zh"]["description"])
    parser.add_argument("--output-dir", type=Path, default=Path("resources/exam_boards/cie"), help=MESSAGES["zh"]["output_dir"])
    parser.add_argument("--no-overview", action="store_true", help=MESSAGES["zh"]["no_overview"])
    parser.add_argument("--delay", type=float, default=0.5, help=MESSAGES["zh"]["delay"])
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help=MESSAGES["zh"]["lang"])
    args = parser.parse_args()
    messages = MESSAGES[args.lang]

    subjects_path, rules_path = sync_catalog(args.output_dir, fetch_overview=not args.no_overview, delay_seconds=args.delay)
    print(f"{messages['subjects']}: {subjects_path}")
    print(f"{messages['rules']}: {rules_path}")


if __name__ == "__main__":
    main()
