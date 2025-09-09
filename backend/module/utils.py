import os, platform, subprocess

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def join(*parts) -> str:
    return os.path.join(*parts)

def open_file(path: str) -> None:
    if not os.path.exists(path):
        return
    sys = platform.system()
    if sys == "Windows":
        os.startfile(path)  # noqa
    elif sys == "Darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])
