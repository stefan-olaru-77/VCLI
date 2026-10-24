"""Small, dependency-free Emmet abbreviation expansion for the editor."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Node:
    tag: str = "div"
    node_id: str = ""
    classes: list[str] = field(default_factory=list)
    text: str = ""
    children: list[Node] = field(default_factory=list)


_PART_RE = re.compile(r"^(?P<tag>[A-Za-z][\w:-]*)?(?P<attrs>(?:[.#][\w-]+)*)(?:\{(?P<text>.*)\})?$")


def _split_top_level(value: str, separator: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(value):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == separator and depth == 0:
            parts.append(value[start:index])
            start = index + 1
    parts.append(value[start:])
    return [part for part in parts if part]


def _parse_atom(value: str) -> Node:
    match = _PART_RE.match(value)
    if not match:
        raise ValueError("invalid abbreviation")
    attrs = match.group("attrs")
    node_id = ""
    classes: list[str] = []
    for marker, name in re.findall(r"([.#])([\w-]+)", attrs):
        if marker == ".":
            classes.append(name)
        else:
            node_id = name
    return Node(
        tag=match.group("tag") or ("div" if attrs else value),
        node_id=node_id,
        classes=classes,
        text=match.group("text") or "",
    )


def _parse(value: str) -> list[Node]:
    siblings = _split_top_level(value, "+")
    if len(siblings) > 1:
        result: list[Node] = []
        for part in siblings:
            result.extend(_parse(part))
        return result

    children = _split_top_level(value, ">")
    if len(children) > 1:
        parents = _parse(children[0])
        descendants = _parse(">".join(children[1:]))
        for parent in parents:
            parent.children.extend(descendants)
        return parents

    match = re.match(r"^(.*?)(?:\*(\d+))?$", value)
    atom = _parse_atom(match.group(1) if match else value)
    count = int(match.group(2) or 1) if match else 1
    result = []
    for index in range(1, count + 1):
        item = Node(atom.tag, atom.node_id, list(atom.classes), atom.text, list(atom.children))
        if "$" in item.text:
            item.text = item.text.replace("$", str(index))
        result.append(item)
    return result


def _render(node: Node, level: int, unit: str, base: str) -> str:
    indent = base + unit * level
    attrs = []
    if node.node_id:
        attrs.append(f'id="{node.node_id}"')
    if node.classes:
        attrs.append(f'class="{" ".join(node.classes)}"')
    opening = f"<{node.tag}{(' ' + ' '.join(attrs)) if attrs else ''}>"
    closing = f"</{node.tag}>"
    if not node.children:
        return f"{indent}{opening}{node.text}{closing}"
    children = "\n".join(_render(child, level + 1, unit, base) for child in node.children)
    return f"{indent}{opening}\n{children}\n{indent}{closing}"


def expand_abbreviation(abbreviation: str, unit: str = "    ", base: str = "") -> str:
    """Expand common tag/class/id, child, sibling and multiplier syntax."""
    abbreviation = abbreviation.strip()
    if not abbreviation:
        raise ValueError("empty abbreviation")
    if abbreviation == "!":
        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            f"{unit}<head>\n{unit}{unit}<meta charset=\"UTF-8\">\n{unit}</head>\n"
            f"{unit}<body>\n{unit}</body>\n"
            "</html>"
        )
    return "\n".join(_render(node, 0, unit, base) for node in _parse(abbreviation))
