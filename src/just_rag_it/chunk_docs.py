import json
import pathlib
import re

from chonkie import RecursiveChunker
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
IN_DIR = ROOT / "data" / "langchain-docs"
OUT_FILE = ROOT / "data" / "chunks" / "langchain-docs.jsonl"
DOCS_BASE = "https://docs.langchain.com/"
TITLE_PATTERN = re.compile(r"^#+\s+(.+)$", re.MULTILINE)

console = Console()


def doc_title(text: str, fallback: str) -> str:
    """取文档里第一个 markdown 标题作为标题，取不到就用文件名。"""
    match = TITLE_PATTERN.search(text)
    return match.group(1).strip() if match else fallback


def main() -> None:
    chunker = RecursiveChunker(tokenizer="gpt2", chunk_size=512)
    files = sorted(IN_DIR.rglob("*.md"))
    if not files:
        console.print(f"[red]没有找到输入文档：{IN_DIR}（先跑 download_example_docs）")
        return

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    total_chunks = 0
    total_tokens = 0

    with OUT_FILE.open("w", encoding="utf-8") as out, Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} 文件"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("chunking", total=len(files))
        for path in files:
            source = path.relative_to(IN_DIR).as_posix()
            text = path.read_text(encoding="utf-8")
            url = DOCS_BASE + source.removesuffix(".md")
            title = doc_title(text, path.stem)

            for index, chunk in enumerate(chunker.chunk(text)):
                record = {
                    "id": f"{source}#{index}",
                    "source": source,
                    "url": url,
                    "title": title,
                    "chunk_index": index,
                    "start_index": chunk.start_index,
                    "end_index": chunk.end_index,
                    "token_count": chunk.token_count,
                    "text": chunk.text,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_chunks += 1
                total_tokens += chunk.token_count

            progress.advance(task)

    table = Table(title="chunk 结果")
    table.add_column("项目")
    table.add_column("值", justify="right")
    table.add_row("文档数", str(len(files)))
    table.add_row("chunk 数", str(total_chunks))
    table.add_row("平均每篇", f"{total_chunks / len(files):.1f}")
    table.add_row("平均 token", f"{total_tokens / total_chunks:.1f}" if total_chunks else "0")
    table.add_row("输出", str(OUT_FILE))
    console.print(table)


if __name__ == "__main__":
    main()
