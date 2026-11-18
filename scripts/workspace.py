"""Resolve historical source labels through the versioned workspace move map."""
from __future__ import annotations
import json
from pathlib import Path, PurePosixPath


def source_path(root: Path, name: str) -> Path:
    root=Path(root).resolve()
    if not isinstance(name,str) or not name or '\\' in name or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
        raise ValueError('unsafe source path')
    manifest=root/'workspace-layout.json'
    mapping={}
    if manifest.is_file():
        data=json.loads(manifest.read_text())
        if data.get('schema')!='engine-workspace-layout.v1' or not isinstance(data.get('paths'),dict):
            raise ValueError('invalid workspace layout')
        mapping=data['paths']
    target=mapping.get(name,name)
    if not isinstance(target,str) or not target or '\\' in target or PurePosixPath(target).is_absolute() or '..' in PurePosixPath(target).parts:
        raise ValueError('unsafe mapped source path')
    path=(root/target).resolve()
    if not path.is_relative_to(root):raise ValueError('source escapes workspace')
    return path
