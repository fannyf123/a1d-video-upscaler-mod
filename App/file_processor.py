import os

SUPPORTED_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv"}


def is_valid_video(path: str) -> bool:
    return (
        os.path.isfile(path) and
        os.path.splitext(path)[1].lower() in SUPPORTED_EXTS
    )


def get_output_dir(input_path: str) -> str:
    out = os.path.join(os.path.dirname(input_path), "OUTPUT")
    os.makedirs(out, exist_ok=True)
    return out


def collect_videos(paths: list) -> list:
    videos = []
    for p in paths:
        if os.path.isfile(p) and is_valid_video(p):
            videos.append(p)
        elif os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    full = os.path.join(root, f)
                    if is_valid_video(full):
                        videos.append(full)
    return videos
