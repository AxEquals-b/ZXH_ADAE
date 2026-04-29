from __future__ import annotations

from pathlib import Path


class ManifestError(ValueError):
    pass


def _split_inline_list(text: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    quote = ""
    for ch in text:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in {"'", '"'}:
            quote = ch
            current.append(ch)
            continue
        if ch == ",":
            items.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    if current:
        items.append("".join(current).strip())
    return [item for item in items if item]


def _parse_scalar(text: str):
    text = text.strip()
    if text == "":
        return ""
    if text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if inner == "":
            return []
        return [_parse_scalar(item) for item in _split_inline_list(inner)]
    if text == "true":
        return True
    if text == "false":
        return False
    if text in {"null", "~"}:
        return None
    if text.lstrip("-").isdigit():
        return int(text)
    try:
        if "." in text or "e" in text or "E" in text:
            return float(text)
    except Exception:
        pass
    return text


def _parse_key(text: str) -> str:
    key = text.strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in {"'", '"'}:
        return key[1:-1]
    return key


class _Parser:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lines: list[tuple[int, str, int]] = []
        self.idx = 0

        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            self.lines.append((indent, raw[indent:].rstrip(), lineno))

    def parse(self):
        if not self.lines:
            return {}
        node = self._parse_block(self.lines[0][0])
        if self.idx != len(self.lines):
            _, _, lineno = self.lines[self.idx]
            raise ManifestError(f"{self.path}:{lineno}: unexpected trailing content")
        return node

    def _parse_block(self, indent: int):
        if self.idx >= len(self.lines):
            raise ManifestError(f"{self.path}: unexpected end of file")
        current_indent, text, _ = self.lines[self.idx]
        if current_indent != indent:
            raise ManifestError(
                f"{self.path}:{self.lines[self.idx][2]}: invalid indentation, expect {indent} spaces"
            )
        if text.startswith("- "):
            return self._parse_list(indent)
        return self._parse_map(indent)

    def _parse_map(self, indent: int) -> dict[str, object]:
        result: dict[str, object] = {}
        while self.idx < len(self.lines):
            current_indent, text, lineno = self.lines[self.idx]
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ManifestError(f"{self.path}:{lineno}: unexpected nested mapping")
            if text.startswith("- "):
                raise ManifestError(f"{self.path}:{lineno}: list item not allowed in mapping")
            key, sep, rest = text.partition(":")
            if not sep:
                raise ManifestError(f"{self.path}:{lineno}: invalid mapping entry")
            key = _parse_key(key)
            rest = rest.strip()
            self.idx += 1
            if rest == "":
                if self.idx < len(self.lines) and self.lines[self.idx][0] > indent:
                    result[key] = self._parse_block(self.lines[self.idx][0])
                else:
                    result[key] = None
            else:
                result[key] = _parse_scalar(rest)
        return result

    def _parse_list(self, indent: int) -> list[object]:
        result: list[object] = []
        while self.idx < len(self.lines):
            current_indent, text, lineno = self.lines[self.idx]
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ManifestError(f"{self.path}:{lineno}: unexpected nested list")
            if not text.startswith("- "):
                break

            item_text = text[2:].strip()
            self.idx += 1
            if item_text == "":
                if self.idx < len(self.lines) and self.lines[self.idx][0] > indent:
                    result.append(self._parse_block(self.lines[self.idx][0]))
                else:
                    result.append(None)
                continue

            key, sep, rest = item_text.partition(":")
            if sep:
                item: dict[str, object] = {_parse_key(key): _parse_scalar(rest.strip())}
                if self.idx < len(self.lines) and self.lines[self.idx][0] > indent:
                    nested = self._parse_block(self.lines[self.idx][0])
                    if not isinstance(nested, dict):
                        raise ManifestError(
                            f"{self.path}:{lineno}: list mapping item requires nested mapping"
                        )
                    item.update(nested)
                result.append(item)
                continue

            result.append(_parse_scalar(item_text))
        return result


def load_manifest(path: str | Path) -> dict:
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    data = _Parser(manifest_path).parse()
    if not isinstance(data, dict):
        raise ManifestError(f"{manifest_path}: manifest root must be a mapping")
    return data
