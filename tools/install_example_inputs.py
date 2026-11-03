"""Install bundled fixtures without overwriting unrelated input files."""
import argparse
import hashlib
import shutil
from pathlib import Path


def install(input_dir):
    target = Path(input_dir).expanduser().resolve()
    if not target.is_dir():
        raise ValueError("Pass an existing ComfyUI input directory.")
    source = Path(__file__).resolve().parents[1] / "examples/inputs"
    files = sorted(source.glob("shot-workspace-example-*"))
    for path in files:
        out = target / path.name
        if out.exists() and (
            not out.is_file()
            or hashlib.sha256(out.read_bytes()).digest()
            != hashlib.sha256(path.read_bytes()).digest()
        ):
            raise FileExistsError(f"Refusing to overwrite different input: {out.name}")
    for path in files:
        out = target / path.name
        if not out.exists():
            shutil.copy2(path, out)
    return [path.name for path in files]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    for name in install(parser.parse_args().input_dir):
        print(name)
