# Embodiment and Destination configuration additions
from .config import settings

# New validators for embodiment and destination arcs
import re
from typing import List, Dict

MOVEMENT_VERBS = [
    "incammin", "avanz", "attravers", "super", "raggiung", "scend", "risal", "volt", "prosegu", "sost"
]
TRANSITION_TOKENS = [
    "più avanti", "oltre il", "svolti", "superi", "raggiungi", "scendi", "risali", "appena dopo", "di fronte", "poco più in là"
]

SENSORY_LEXICON = {
    "corporeo": ["pied", "mani", "spalle", "respiro", "petto", "palpebre", "collo", "schiena"],
    "ambientale": ["luce", "suono", "fruscio", "profumo", "odore", "aria", "erba", "acqua", "foglia"]
}

class EmbodimentValidator:
    def validate_beat(self, text: str) -> Dict:
        t = text.lower()
        has_movement = any(v in t for v in MOVEMENT_VERBS)
        has_transition = any(tok in t for tok in TRANSITION_TOKENS)
        has_corp = any(w in t for w in SENSORY_LEXICON["corporeo"])
        has_env = any(w in t for w in SENSORY_LEXICON["ambientale"])
        has_sensory_coupling = has_corp and has_env
        has_downshift = any(k in t for k in ["respiro", "rilassa", "si allunga", "si scioglie", "più lento"]) 
        second_person = (" ti " in f" {t} ") or t.strip().startswith("ti ") or (" i tuoi" in t)
        score = sum([has_movement, has_transition, has_sensory_coupling, has_downshift, second_person])
        return {
            "ok": score >= 4,
            "score": score,
            "checks": {
                "movement": has_movement,
                "transition": has_transition,
                "sensory_coupling": has_sensory_coupling,
                "downshift": has_downshift,
                "second_person": second_person
            }
        }

class DestinationValidator:
    ARRIVAL_TOKENS = ["hai raggiunto", "sei arrivato", "arrivi", "raggiungi", "giungi"]
    PROGRESS_TOKENS = ["più vicino", "più avanti", "verso", "in lontan", "si avvicina", "approssimi", "ti avvicini"]
    PROMISE_TOKENS = ["stanotte", "questa notte", "questa sera", "questa camminata", "questa passeggiata"]

    def _detect_destination_promise(self, text: str) -> bool:
        t = text.lower()
        return any(tok in t for tok in self.PROMISE_TOKENS) and any(tok in t for tok in ["verso", "raggiungere", "meta", "destinazione"])    

    def _detect_progress_markers(self, text: str) -> bool:
        t = text.lower()
        return any(tok in t for tok in self.PROGRESS_TOKENS)

    def _detect_arrival_language(self, text: str) -> bool:
        t = text.lower()
        return any(tok in t for tok in self.ARRIVAL_TOKENS)

    def validate_destination_arc(self, beats: List[Dict]) -> Dict:
        texts = [b.get("text", "") for b in beats]
        has_setup = any(self._detect_destination_promise(x) for x in texts[:2]) if len(texts) >= 2 else False
        has_progress = any(self._detect_progress_markers(x) for x in texts[2:-2]) if len(texts) > 4 else False
        has_arrival = any(self._detect_arrival_language(x) for x in texts[-3:]) if len(texts) >= 1 else False
        ok = has_setup and has_progress and has_arrival
        missing = []
        if not has_setup: missing.append("destination_setup")
        if not has_progress: missing.append("journey_progress")
        if not has_arrival: missing.append("arrival_closure")
        return {
            "ok": ok,
            "missing": missing
        }
