from __future__ import annotations

from typing import Dict, List, Optional, Tuple


def build_sequence(
    song_messages: List[Dict],
    anchor_index: int,
    max_gap_hours: Optional[int] = None,
    max_songs: Optional[int] = None,
) -> Tuple[Dict, List[Dict], int, str]:
    if not song_messages:
        raise ValueError("歌曲消息列表为空")
    if anchor_index < 0 or anchor_index >= len(song_messages):
        raise ValueError("起点编号越界")
    anchor = song_messages[anchor_index]
    result: List[Dict] = []
    seen_song_ids = set()
    skipped_duplicates = 0
    stop_reason = "到达消息末尾"
    prev_kept_item = None

    for item in song_messages[anchor_index:]:
        if item["uid"] != anchor["uid"]:
            continue
        if prev_kept_item is not None and max_gap_hours is not None:
            gap_seconds = item["msg_time_ms"] - prev_kept_item["msg_time_ms"]
            gap_hours = gap_seconds / 1000 / 3600
            if gap_hours > max_gap_hours:
                stop_reason = f"相邻歌曲时间间隔超过 {max_gap_hours} 小时"
                break
        if item["song_id"] in seen_song_ids:
            skipped_duplicates += 1
            continue
        seen_song_ids.add(item["song_id"])
        result.append(item)
        prev_kept_item = item
        if max_songs is not None and len(result) >= max_songs:
            stop_reason = f"达到最大歌曲数量限制 {max_songs}"
            break
    return anchor, result, skipped_duplicates, stop_reason
