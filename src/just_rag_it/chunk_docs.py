import argparse
import json
import pathlib
import re
import tomllib

from chonkie import RecursiveChunker, TokenChunker

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG = ROOT / "config" / "chunking.toml"
TITLE_PATTERN = re.compile(r"^#+\s+(.+)$", re.MULTILINE)
CHUNKERS = {"recursive": RecursiveChunker, "token": TokenChunker}


def resolve(path: str) -> pathlib.Path:
    """配置里的相对路径一律相对仓库根目录。"""
    candidate = pathlib.Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def load_config(path: pathlib.Path) -> dict:
    with path.open("rb") as file:
        return tomllib.load(file)


def build_chunker(config: dict):
    params = dict(config)
    name = params.pop("type", "recursive")
    if name not in CHUNKERS:
        raise SystemExit(f"未知的 chunker 类型：{name}，可选：{', '.join(CHUNKERS)}")
    return CHUNKERS[name](**params)


def doc_title(text: str, fallback: str) -> str:
    """取文档里第一个 markdown 标题作为标题，取不到就用文件名。"""
    match = TITLE_PATTERN.search(text)
    return match.group(1).strip() if match else fallback


def main() -> None:
    parser = argparse.ArgumentParser(description="按配置切分已下载的 markdown 文档")
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        default=DEFAULT_CONFIG,
        help=f"配置文件路径（默认 {DEFAULT_CONFIG.relative_to(ROOT)}）",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    chunker = build_chunker(config.get("chunker", {}))

    in_dir = resolve(config["input"]["dir"])
    docs_base = config["input"].get("docs_base", "")
    out_file = resolve(config["output"]["dir"]) / config["output"]["file"]

    files = sorted(in_dir.glob(config["input"]["glob"]))
    if not files:
        raise SystemExit(f"没有找到输入文档：{in_dir}（先跑 download_example_docs）")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    total_chunks = 0
    total_tokens = 0

    with out_file.open("w", encoding="utf-8") as out:
        for path in files:
            source = path.relative_to(in_dir).as_posix()
            text = path.read_text(encoding="utf-8")
            title = doc_title(text, path.stem)

            for index, chunk in enumerate(chunker.chunk(text)):
                record = {
                    "id": f"{source}#{index}",
                    "source": source,
                    "url": docs_base + source.removesuffix(".md"),
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

    print(f"文档 {len(files)} 篇")
    print(f"chunk {total_chunks} 个（平均每篇 {total_chunks / len(files):.1f}）")
    if total_chunks:
        print(f"平均 token {total_tokens / total_chunks:.1f}")
    print(f"输出 {out_file}")


if __name__ == "__main__":
    main()
