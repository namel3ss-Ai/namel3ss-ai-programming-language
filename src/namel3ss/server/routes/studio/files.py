from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ...deps import Principal, Role, can_view_pages, get_principal
from ...schemas import CodeTransformRequest, StudioFileRequest, StudioFileResponse, StudioTreeNode, UIGenerateRequest


def register_file_routes(
    router: APIRouter,
    *,
    project_root: Callable[[], Path],
    project_ui_manifest_fn: Callable[[], Dict[str, Any]],
    iter_ai_files_fn: Callable[[Path], list[Path]],
    ignored_dirs: set[str],
    invalidate_program_cache: Callable[[], None],
) -> None:
    """Register file and UI editing routes."""

    def _safe_path(rel_path: str) -> Path:
        base = project_root()
        target = (base / rel_path).resolve()
        if base not in target.parents and base != target:
            raise HTTPException(status_code=400, detail="Invalid path")
        return target

    def _find_element_by_id(pages: list[dict[str, Any]], element_id: str) -> dict[str, Any] | None:
        for page in pages:
            stack = list(page.get("layout", []))
            while stack:
                el = stack.pop()
                if isinstance(el, dict) and el.get("id") == element_id:
                    el["page"] = page.get("name")
                    el["page_route"] = page.get("route")
                    el["source_path"] = el.get("source_path") or page.get("source_path")
                    return el
                if isinstance(el, dict):
                    stack.extend(el.get("layout", []))
                    stack.extend(el.get("when", []))
                    stack.extend(el.get("otherwise", []))
        return None

    def _replace_string_value(text: str, old: str, new: str) -> str:
        target = f'"{old}"'
        replacement = f'"{new}"'
        if target not in text:
            return text
        return text.replace(target, replacement, 1)

    def _element_pattern(el: dict[str, Any]) -> str | None:
        t = el.get("type")
        if t == "heading":
            return f'heading "{el.get("text", "")}"'
        if t == "text":
            return f'text "{el.get("text", "")}"'
        if t == "button":
            return f'button "{el.get("label", "")}"'
        if t == "input":
            return f'input "{el.get("label", "")}'
        if t == "section":
            return f'section "{el.get("name", "")}"'
        return None

    def _find_line_index(lines: list[str], target_el: dict[str, Any]) -> int:
        pattern = _element_pattern(target_el)
        if not pattern:
            return -1
        for idx, line in enumerate(lines):
            if pattern in line.strip():
                return idx
        return -1

    def _render_new_element(data: dict[str, Any], indent: str) -> str:
        t = data.get("type")
        if t == "heading":
            return f'{indent}heading "{data.get("properties", {}).get("label", "New heading")}"'
        if t == "text":
            return f'{indent}text "{data.get("properties", {}).get("text", "New text")}"'
        if t == "button":
            return f'{indent}button "{data.get("properties", {}).get("label", "New button")}"'
        if t == "input":
            label = data.get("properties", {}).get("label", "New field")
            return f'{indent}input "{label}" as field'
        if t == "section":
            name = data.get("properties", {}).get("label", "Section")
            return f'{indent}section "{name}":'
        return f'{indent}text "New"'

    def _build_tree(directory: Path, base: Path) -> Optional[StudioTreeNode]:
        children: list[StudioTreeNode] = []
        for entry in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
            if entry.name in ignored_dirs:
                continue
            if entry.is_dir():
                child = _build_tree(entry, base)
                if child and child.children:
                    children.append(child)
                elif child and directory == base:
                    continue
            else:
                if entry.suffix != ".ai":
                    continue
                rel = entry.relative_to(base)
                children.append(
                    StudioTreeNode(
                        name=entry.name,
                        path=str(rel).replace("\\", "/"),
                        type="file",
                        kind=None,
                        children=None,
                    )
                )
        rel_dir = directory.relative_to(base) if directory != base else Path(".")
        return StudioTreeNode(
            name=directory.name if directory != base else base.name,
            path=str(rel_dir).replace("\\", "/"),
            type="directory",
            kind=None,
            children=children,
        )

    @router.post("/api/studio/code/transform")
    def api_code_transform(payload: CodeTransformRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        base = project_root()
        target = (base / payload.path).resolve()
        if base not in target.parents and base != target:
            raise HTTPException(status_code=400, detail="Invalid path")
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        manifest = project_ui_manifest_fn()
        el = None
        if payload.element_id:
            el = _find_element_by_id(manifest.get("pages", []), payload.element_id)
        try:
            content = target.read_text(encoding="utf-8")
            op = payload.op or "update_property"
            new_element_id = None
            if op == "update_property":
                if not el:
                    raise HTTPException(status_code=404, detail="Element not found")
                prop = payload.property
                if prop in ("label", "text"):
                    old_val = el.get("label") or el.get("text") or ""
                    content = _replace_string_value(content, old_val, payload.new_value or "")
                elif prop == "color":
                    old_val = None
                    for s in el.get("styles", []):
                        if s.get("kind") == "color":
                            old_val = s.get("value")
                    if old_val is None:
                        raise HTTPException(status_code=400, detail="Property not found")
                    content = content.replace(str(old_val), payload.new_value or "", 1)
                elif prop == "layout":
                    old_layout = None
                    for s in el.get("styles", []):
                        if s.get("kind") == "layout":
                            old_layout = s.get("value")
                    if old_layout:
                        content = content.replace(f"layout is {old_layout}", f"layout is {payload.new_value}", 1)
                    else:
                        raise HTTPException(status_code=400, detail="Property not found")
                else:
                    raise HTTPException(status_code=400, detail="Unsupported property")
            elif op in {"insert_element", "delete_element", "move_element"}:
                lines = content.splitlines()
                indent_unit = "  "

                def find_line_for_element(target_el: dict[str, Any]) -> int:
                    pattern = _element_pattern(target_el)
                    if not pattern:
                        return -1
                    for idx, line in enumerate(lines):
                        if pattern in line.strip():
                            return idx
                    return -1

                if op == "insert_element":
                    position = payload.position or "after"
                    template = _render_new_element(payload.new_element or {}, indent_unit)
                    insert_at = len(lines)
                    if el and position in {"before", "after"}:
                        idx = find_line_for_element(el)
                        if idx >= 0:
                            insert_at = idx + (1 if position == "after" else 0)
                    if insert_at > len(lines):
                        lines.append(template)
                    else:
                        lines.insert(insert_at, template)
                    new_element_id = "pending"
                elif op == "delete_element":
                    if not el:
                        raise HTTPException(status_code=404, detail="Element not found")
                    idx = find_line_for_element(el)
                    if idx >= 0:
                        del lines[idx]
                    else:
                        raise HTTPException(status_code=400, detail="Cannot locate element")
                elif op == "move_element":
                    direction = payload.position or "after"
                    if not el:
                        raise HTTPException(status_code=404, detail="Element not found")
                    idx = find_line_for_element(el)
                    if idx < 0:
                        raise HTTPException(status_code=400, detail="Cannot locate element")
                    if direction == "up" and idx > 0:
                        lines[idx - 1], lines[idx] = lines[idx], lines[idx - 1]
                    elif direction == "down" and idx < len(lines) - 1:
                        lines[idx + 1], lines[idx] = lines[idx], lines[idx + 1]
                content = "\n".join(lines) + ("\n" if content.endswith("\n") else "")
            else:
                raise HTTPException(status_code=400, detail="Unsupported operation")
            target.write_text(content, encoding="utf-8")
            invalidate_program_cache()
            manifest = project_ui_manifest_fn()
            return {"success": True, "manifest": manifest, "new_element_id": new_element_id}
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/studio/ui/generate")
    def api_ui_generate(payload: UIGenerateRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        base = project_root()
        target = (base / payload.page_path).resolve()
        if base not in target.parents and base != target:
            raise HTTPException(status_code=400, detail="Invalid path")
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        manifest = project_ui_manifest_fn()
        selected_el = None
        if payload.selected_element_id:
            selected_el = _find_element_by_id(manifest.get("pages", []), payload.selected_element_id)
            if selected_el is None:
                raise HTTPException(status_code=404, detail="Element not found")
        try:
            content = target.read_text(encoding="utf-8")
            lines = content.splitlines()
            indent_unit = "  "
            insert_idx = len(lines)
            insert_indent = indent_unit
            if selected_el:
                idx = _find_line_index(lines, selected_el)
                if idx >= 0:
                    line = lines[idx]
                    leading = len(line) - len(line.lstrip(" "))
                    insert_indent = line[:leading]
                    insert_idx = idx + 1
                    if selected_el.get("type") == "section":
                        insert_indent = insert_indent + indent_unit
            prompt_text = payload.prompt.strip()
            if not prompt_text:
                prompt_text = "Generated UI"
            snippet = [
                f'{insert_indent}heading "AI Generated"',
                f'{insert_indent}text "{prompt_text[:60]}"',
            ]
            lines[insert_idx:insert_idx] = snippet
            content_out = "\n".join(lines) + ("\n" if content.endswith("\n") else "")
            target.write_text(content_out, encoding="utf-8")
            invalidate_program_cache()
            manifest = project_ui_manifest_fn()
            return {"success": True, "manifest": manifest}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/studio/files")
    def api_studio_files(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        root = project_root()
        tree = _build_tree(root, root)
        if not tree:
            raise HTTPException(status_code=500, detail="Unable to scan project")
        return {"root": tree}

    @router.get("/api/studio/file", response_model=StudioFileResponse)
    def api_studio_get_file(
        path: str = Query(..., description="Project-root-relative path"), principal: Principal = Depends(get_principal)
    ) -> StudioFileResponse:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        target = _safe_path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        return StudioFileResponse(path=path, content=target.read_text(encoding="utf-8"))

    @router.post("/api/studio/file", response_model=StudioFileResponse)
    def api_studio_save_file(payload: StudioFileRequest, principal: Principal = Depends(get_principal)) -> StudioFileResponse:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        target = _safe_path(payload.path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        target.write_text(payload.content, encoding="utf-8")
        invalidate_program_cache()
        return StudioFileResponse(path=payload.path, content=payload.content)


__all__ = ["register_file_routes"]
