import json
import os
import threading
from typing import Any, Dict, List, Optional

_LOCK = threading.RLock()

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "queue_data.json")


class PersistentQueue:
    """
    Thread-safe JSON store for per-guild queues and minimal now-playing state.
    Data shape:
        {
            "<guild_id>": {
                "queue": [ {"title": str, "uri": str, "duration": int, "identifier": str, "author": str, "requester": int} ],
                "index": int,  # current playback index into queue
                "loop": 0|1|2,
                "shuffle": bool,
                "volume": int
            }
        }
    """

    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        # ensure file exists
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _read(self) -> Dict[str, Any]:
        with _LOCK:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}

    def _write(self, data: Dict[str, Any]) -> None:
        with _LOCK:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    def get_guild(self, guild_id: int) -> Dict[str, Any]:
        data = self._read()
        key = str(guild_id)
        g = data.get(key) or {}
        if not g:
            g = {"queue": [], "index": 0, "loop": 0, "shuffle": False, "volume": 70}
            data[key] = g
            self._write(data)
        return g

    def set_guild_prop(self, guild_id: int, key: str, value: Any) -> None:
        data = self._read()
        gid = str(guild_id)
        g = data.get(gid) or {"queue": [], "index": 0, "loop": 0, "shuffle": False, "volume": 70}
        g[key] = value
        data[gid] = g
        self._write(data)

    def clear_guild(self, guild_id: int) -> None:
        data = self._read()
        gid = str(guild_id)
        data[gid] = {"queue": [], "index": 0, "loop": 0, "shuffle": False, "volume": 70}
        self._write(data)

    # Queue operations
    def get_queue(self, guild_id: int) -> List[Dict[str, Any]]:
        return list(self.get_guild(guild_id).get("queue", []))

    def get_index(self, guild_id: int) -> int:
        return int(self.get_guild(guild_id).get("index", 0))

    def set_index(self, guild_id: int, index: int) -> None:
        self.set_guild_prop(guild_id, "index", int(index))

    def append_track(self, guild_id: int, track: Dict[str, Any]) -> None:
        data = self._read()
        gid = str(guild_id)
        g = data.get(gid) or {"queue": [], "index": 0, "loop": 0, "shuffle": False, "volume": 70}
        g.setdefault("queue", []).append(track)
        data[gid] = g
        self._write(data)

    def extend_tracks(self, guild_id: int, tracks: List[Dict[str, Any]]) -> None:
        data = self._read()
        gid = str(guild_id)
        g = data.get(gid) or {"queue": [], "index": 0, "loop": 0, "shuffle": False, "volume": 70}
        g.setdefault("queue", []).extend(tracks)
        data[gid] = g
        self._write(data)

    def current_track(self, guild_id: int) -> Optional[Dict[str, Any]]:
        g = self.get_guild(guild_id)
        idx = int(g.get("index", 0))
        q = g.get("queue") or []
        if 0 <= idx < len(q):
            return q[idx]
        return None

    def next_index(self, guild_id: int) -> int:
        g = self.get_guild(guild_id)
        idx = int(g.get("index", 0))
        q = g.get("queue") or []
        loop = int(g.get("loop", 0))
        if not q:
            return 0
        if loop == 1:  # track loop
            return idx
        if idx + 1 < len(q):
            return idx + 1
        if loop == 2:  # queue loop
            return 0
        # no loop, end
        return len(q)  # points past end

    def remove_at(self, guild_id: int, index: int) -> Optional[Dict[str, Any]]:
        data = self._read()
        gid = str(guild_id)
        g = data.get(gid) or {}
        q = g.get("queue") or []
        if 0 <= index < len(q):
            t = q.pop(index)
            # adjust index pointer
            cur = int(g.get("index", 0))
            if index < cur:
                cur -= 1
            elif index == cur:
                # keep pointer at same numeric index which now points to next item
                pass
            g["index"] = max(0, min(cur, len(q)))
            g["queue"] = q
            data[gid] = g
            self._write(data)
            return t
        return None

    def set_queue(self, guild_id: int, tracks: List[Dict[str, Any]]) -> None:
        """Replace the entire queue with new tracks."""
        data = self._read()
        gid = str(guild_id)
        g = data.get(gid) or {"queue": [], "index": 0, "loop": 0, "shuffle": False, "volume": 70}
        g["queue"] = tracks
        # Ensure index is within bounds
        g["index"] = max(0, min(g.get("index", 0), len(tracks) - 1)) if tracks else 0
        data[gid] = g
        self._write(data)

