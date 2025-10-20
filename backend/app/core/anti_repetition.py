from typing import Dict, List, Set
import random
import re
from collections import defaultdict

class AntiRepetitionSystem:
    """Sistema per evitare ripetizioni nella generazione delle storie"""
    
    def __init__(self):
        self.used_phrases = set()
        self.recent_actions = []
        self.opener_usage = defaultdict(int)
        self.beat_patterns = []
        self.forbidden_starts = set()
        
    def track_beat_content(self, beat_text: str, beat_index: int):
        """Analizza e traccia il contenuto di un beat per evitare ripetizioni"""
        # Estrai pattern comuni
        sentences = self._extract_sentences(beat_text)
        
        for sentence in sentences:
            # Traccia opener comuni
            opener = self._extract_opener(sentence)
            if opener:
                self.opener_usage[opener] += 1
                if self.opener_usage[opener] > 2:
                    self.forbidden_starts.add(opener)
                    
        # Traccia azioni e verbi
        actions = self._extract_actions(beat_text)
        self.recent_actions.extend(actions)
        if len(self.recent_actions) > 10:
            self.recent_actions = self.recent_actions[-10:]
            
        # Memorizza pattern del beat
        self.beat_patterns.append({
            "index": beat_index,
            "opener": self._extract_opener(beat_text),
            "main_action": self._extract_main_action(beat_text),
            "sensory_elements": self._extract_sensory_elements(beat_text)
        })
        
    def get_forbidden_phrases(self) -> List[str]:
        """Restituisce le frasi da evitare nella prossima generazione"""
        forbidden = list(self.forbidden_starts)
        
        # Aggiungi azioni recenti più usate
        action_counts = defaultdict(int)
        for action in self.recent_actions:
            action_counts[action] += 1
            
        for action, count in action_counts.items():
            if count >= 3:
                forbidden.append(action)
                
        return forbidden
        
    def generate_unique_elements(self, sensory_focus: str, waypoint: str, beat_index: int) -> Dict[str, str]:
        """Genera elementi unici per il beat corrente"""
        
        # Elementi sensory diversificati
        sensory_elements = {
            "sight": [
                "dappled light filtering through", "gentle shadows dancing", "soft gleam reflecting", 
                "distant shimmer catching", "warm glow emanating", "subtle patterns emerging",
                "peaceful vista opening", "tranquil scene unfolding"
            ],
            "sound": [
                "whispered breeze carrying", "distant rustle suggesting", "soft murmur echoing", 
                "gentle echo resonating", "rhythmic patter creating", "melodic hum surrounding",
                "soothing cadence flowing", "harmonious blend arising"
            ],
            "touch": [
                "warm embrace enveloping", "cool caress touching", "gentle pressure guiding", 
                "soft texture welcoming", "smooth surface supporting", "tender contact reassuring",
                "comforting sensation spreading", "delicate touch soothing"
            ],
            "smell": [
                "earthy fragrance drifting", "sweet scent lingering", "fresh aroma surrounding",
                "subtle perfume wafting", "natural essence filling", "pleasant bouquet greeting"
            ],
            "proprioception": [
                "body naturally settling", "muscles gently releasing", "breathing gradually slowing",
                "posture softly adjusting", "weight comfortably shifting", "tension peacefully dissolving"
            ]
        }
        
        # Movement verbs diversificati
        movement_verbs = [
            "ti incammini verso", "procedi lungo", "attraversi dolcemente", "raggiungi serenamente",
            "ti dirigi verso", "avanzi attraverso", "scivoli oltre", "ti sposti verso",
            "cammini fino a", "approdi a", "giungi presso", "arrivi in prossimità di"
        ]
        
        # Transition connectors diversificati  
        transitions = [
            "più avanti", "oltre il", "proseguendo", "continuando il cammino",
            "addentrandoti", "seguendo il sentiero", "attraversando", "superando",
            "man mano che procedi", "mentre avanzi", "nel tuo procedere"
        ]
        
        # Seleziona elementi non usati di recente
        available_sensory = [elem for elem in sensory_elements.get(sensory_focus, []) 
                           if elem not in [p.get("sensory_elements", {}).get(sensory_focus) 
                                          for p in self.beat_patterns[-3:]]]
        
        available_movements = [verb for verb in movement_verbs 
                             if verb not in [p.get("main_action") for p in self.beat_patterns[-3:]]]
        
        available_transitions = [trans for trans in transitions 
                               if trans not in [p.get("main_action") for p in self.beat_patterns[-2:]]]
        
        return {
            "unique_sensory": random.choice(available_sensory) if available_sensory else sensory_elements[sensory_focus][0],
            "unique_movement": random.choice(available_movements) if available_movements else movement_verbs[0],
            "unique_transition": random.choice(available_transitions) if available_transitions else transitions[0],
            "waypoint_variation": self._vary_waypoint(waypoint, beat_index)
        }
        
    def _extract_sentences(self, text: str) -> List[str]:
        """Estrae le frasi dal testo"""
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
        
    def _extract_opener(self, text: str) -> str:
        """Estrae l'opener di una frase"""
        if not text:
            return ""
        words = text.split()[:6]
        return " ".join(words).lower().strip()
        
    def _extract_actions(self, text: str) -> List[str]:
        """Estrae azioni/verbi dal testo"""
        action_patterns = [
            r'\b(incammin\w+|avanzi|attraversi|raggiungi|procedi|cammini)\b',
            r'\b(senti\w*|percepisci|noti|osservi|ascolti)\b',
            r'\b(respiri|rilassi|ti\s+fermi|ti\s+soffermi)\b'
        ]
        
        actions = []
        for pattern in action_patterns:
            matches = re.findall(pattern, text.lower())
            actions.extend(matches)
        return actions
        
    def _extract_main_action(self, text: str) -> str:
        """Estrae l'azione principale del testo"""
        actions = self._extract_actions(text)
        return actions[0] if actions else ""
        
    def _extract_sensory_elements(self, text: str) -> Dict[str, str]:
        """Estrae elementi sensory dal testo"""
        sensory_words = {
            "sight": ["vedi", "osservi", "noti", "luce", "ombra", "colore"],
            "sound": ["senti", "ascolti", "suono", "rumore", "melodia", "eco"],
            "touch": ["tocchi", "senti", "morbido", "caldo", "fresco", "texture"],
            "smell": ["profumo", "odore", "fragranza", "aroma"],
            "proprioception": ["equilibrio", "postura", "muscoli", "respiro"]
        }
        
        found_elements = {}
        text_lower = text.lower()
        
        for sense, words in sensory_words.items():
            for word in words:
                if word in text_lower:
                    found_elements[sense] = word
                    break
                    
        return found_elements
        
    def _vary_waypoint(self, waypoint: str, beat_index: int) -> str:
        """Varia la descrizione del waypoint per evitare ripetizioni"""
        if not waypoint:
            return waypoint
            
        variations = {
            "forest": ["bosco", "foresta", "area boschiva", "zona silvestre"],
            "path": ["sentiero", "cammino", "traccia", "via", "percorso"],
            "clearing": ["radura", "spazio aperto", "piccola piazza", "area libera"],
            "bridge": ["ponte", "attraversamento", "passaggio", "collegamento"],
            "stream": ["ruscello", "corso d'acqua", "rivolo", "torrente"]
        }
        
        # Trova la chiave più appropriata
        for key, variants in variations.items():
            if key in waypoint.lower():
                return random.choice(variants)
                
        return waypoint
        
    def should_regenerate_beat(self, proposed_text: str) -> bool:
        """Determina se un beat proposto è troppo simile ai precedenti"""
        if not proposed_text:
            return True
            
        proposed_opener = self._extract_opener(proposed_text)
        
        # Controlla se l'opener è nella blacklist
        if proposed_opener in self.forbidden_starts:
            return True
            
        # Controlla similarità con beat recenti
        recent_patterns = self.beat_patterns[-3:]
        for pattern in recent_patterns:
            similarity_score = self._calculate_similarity(proposed_text, pattern)
            if similarity_score > 0.7:  # Soglia di similarità
                return True
                
        return False
        
    def _calculate_similarity(self, text: str, pattern: Dict) -> float:
        """Calcola similarità tra testo e pattern precedente"""
        text_opener = self._extract_opener(text)
        text_action = self._extract_main_action(text)
        
        pattern_opener = pattern.get("opener", "")
        pattern_action = pattern.get("main_action", "")
        
        opener_sim = 1.0 if text_opener == pattern_opener else 0.0
        action_sim = 1.0 if text_action == pattern_action else 0.0
        
        return (opener_sim + action_sim) / 2.0