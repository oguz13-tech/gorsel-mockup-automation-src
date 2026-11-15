"""Measure recent production reports and optionally persist a safe worker profile.

This tool never opens the live template DB and never changes images.  Writing a
profile requires --write-profile plus an explicit pixel-equivalence marker in
the input JSON, so a benchmark cannot silently promote a faster but different
renderer.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'MERKEZ'))
from URETIM_V4.performance_v501 import machine_identity, machine_key, summarize_reports
from URETIM_V4.unified_batch import production_render_workers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--report-dir', type=Path, required=True)
    parser.add_argument('--profile-root', type=Path, required=True)
    parser.add_argument('--write-profile', action='store_true')
    parser.add_argument('--pixel-equivalence-json', type=Path)
    args = parser.parse_args()
    rows = summarize_reports(args.report_dir)
    groups = {}
    for row in rows:
        if row['failed'] == 0 and row.get('workers'):
            groups.setdefault(int(row['workers']), []).append(row)
    summary = []
    for workers, group in sorted(groups.items()):
        summary.append({'workers': workers, 'runs': len(group),
                        'median_wall_seconds': median(r['wall_seconds'] for r in group),
                        'median_seconds_per_output': median(r['seconds_per_output'] for r in group),
                        'median_outputs_per_minute': median(r['outputs_per_minute'] for r in group)})
    if not summary:
        raise SystemExit('No successful timed reports found.')
    fastest_observed = min(summary, key=lambda row: row['median_seconds_per_output'])
    fixed_workers, fixed_reason = production_render_workers()
    result = {'schema': 1, 'machine_key': machine_key(),
              'machine': machine_identity(), 'samples': summary,
              'recommended_workers': fixed_workers,
              'fixed_profile_reason': fixed_reason,
              'fastest_observed_workers': fastest_observed['workers'],
              'pixel_equivalence_verified': False}
    if args.pixel_equivalence_json:
        marker = json.loads(args.pixel_equivalence_json.read_text(encoding='utf-8'))
        result['pixel_equivalence_verified'] = marker.get('pixel_equivalence_verified') is True
        result['equivalence_evidence'] = str(args.pixel_equivalence_json.resolve())
    if args.write_profile:
        if not result['pixel_equivalence_verified']:
            raise SystemExit('Refusing profile write without pixel-equivalence evidence.')
        args.profile_root.mkdir(parents=True, exist_ok=True)
        target = args.profile_root / 'render_worker_profile.json'
        temp = target.with_suffix('.tmp')
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(target)
        result['written_profile'] = str(target)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
