"""Evidence policy; infrastructure guards and per-event validation are independent."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    independent_seconds: int = 3600
    productive_runs: int = 2
    observations: int = 3
    low_volume_runs: int = 3
    completeness: int = 45
    confidence: float = .65
    max_defect_ratio: float = .35
    degradation_runs: int = 3
    probation_seconds: int = 3600
    trusted_seconds: int = 21600
    dormant_seconds: int = 86400
    max_graph_depth: int = 2


POLICY = Policy()
# These are successful exclusions, not evidence of an extraction defect.
NEUTRAL_REJECTIONS = ('start_date_already_in_the_past', 'no_local_evidence',
                      'outside_bratislava', 'coordinates_outside_bratislava')


def evidence(stats):
    accepted = stats.get('quality/unique_events', 0)
    future = stats.get('quality/unique_future_events', 0)
    neutral = sum(stats.get('validation/rejected/' + key, 0) for key in NEUTRAL_REJECTIONS)
    defects = max(0, stats.get('validation/rejected', 0) - neutral)
    mean = stats.get('quality/score_total', 0) / max(stats.get('quality/events', 0), 1)
    confidence = stats.get('quality/confidence_total', 0) / max(stats.get('quality/events', 0), 1)
    blockers = []
    if not future: blockers.append('no_validated_future_observations')
    if mean < POLICY.completeness: blockers.append('incomplete_extraction')
    if confidence < POLICY.confidence: blockers.append('low_extraction_confidence')
    if defects / max(accepted + defects, 1) > POLICY.max_defect_ratio: blockers.append('integrity_defects')
    return accepted, future, blockers


def priority(row):
    import json
    from crawler.discovery import endpoint_rank
    metrics = json.loads(row['metrics'])
    return (min(40, metrics.get('quality/unique_future_events', 0)*5)
            + (30 if row['status'] in ('probation','trusted') else 0)
            + endpoint_rank(row['url']) / 10 - row['failures']*15
            - min(10, metrics.get('elapsed_time_seconds',0)/12))
