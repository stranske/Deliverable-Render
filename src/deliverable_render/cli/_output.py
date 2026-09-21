"""Safe publication shared by local rendering commands."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def publish(output: Path, content: bytes, inputs: tuple[Path, ...], *, force: bool = False) -> None:
    target = output.resolve()
    if any(target == item.resolve() for item in inputs):
        raise ValueError("output path aliases a rendering input")
    if output.exists() and not force:
        raise ValueError(f"output already exists: {output} (pass --force to replace)")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.replace(name, output)
    finally:
        Path(name).unlink(missing_ok=True)
