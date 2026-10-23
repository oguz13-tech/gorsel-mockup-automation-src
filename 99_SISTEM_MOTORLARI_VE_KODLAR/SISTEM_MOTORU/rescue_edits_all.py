# -*- coding: utf-8 -*-
"""Legacy rescue_edits_all.py: preserved SAFE entrypoint for recovery previews.

The historical script previously wrote over current settings or physically
removed backups at import. Its mutating implementation is intentionally not
executed. Review the snapshot comparison before a separately approved restore.
"""

try:
    from .legacy_recovery_preview import inspect, main
except ImportError:
    from legacy_recovery_preview import inspect, main


def preview(runtime_root=None):
    return inspect("rescue_edits_all.py", runtime_root)


if __name__ == "__main__":
    raise SystemExit(main("rescue_edits_all.py"))
