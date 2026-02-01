from typing import Dict, Any


def verify_card(card: Dict[str, Any], evidence_map: Dict[str, Dict[str, Any]]) -> bool:
    key_points = card.get("key_points") or []
    citations = card.get("citations") or []
    for idx, _ in enumerate(key_points):
        point_cits = [c for c in citations if c.get("key_point_index") == idx]
        if not point_cits:
            return False
        for cit in point_cits:
            eu_id = cit.get("evidence_unit_id")
            if eu_id not in evidence_map:
                return False
            if "start_ms" not in cit or "end_ms" not in cit:
                return False
            eu = evidence_map[eu_id]
            if cit["start_ms"] < eu["start_ms"] or cit["end_ms"] > eu["end_ms"]:
                return False
    return True
