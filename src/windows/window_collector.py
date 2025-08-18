from typing import List, Dict, Optional
import sys
import os

# Ajouter src au path pour import
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from text_validator import TextValidator


class WindowCollector:
    def __init__(self, debug=False, characters_file="characters.json", players_file="players.json", restricted_players_file=None):
        self.debug = debug
        self.current_window = []
        self.validated_rounds = []
        self.collecting = False
        self.last_timer_frame = None

        # Paramètres configurables pour tests
        self.timer_high_threshold = 95  # Timer considéré comme "haut" pour démarrage
        self.timer_low_threshold = 50   # Timer considéré comme "bas"
        self.buffer_size = 5           # Frames avant/après pour validation
        self.gap_threshold = 30        # Secondes de gap pour déclencher collecte
        self.coherence_threshold = 0.7  # 70% de cohérence minimum

        # Nouveau : tracking des timers pour comparaison séquentielle
        self.timer_history = []         # Historique des derniers timers (pour lissage)
        self.window_start_timer = None  # Timer de début de fenêtre courante
        self.timer_jump_threshold = 20  # Saut de timer considéré comme nouveau round

        # Initialiser le validateur de texte pour nettoyage OCR
        self.text_validator = TextValidator(
            characters_file=characters_file,
            players_database_file=players_file,
            restricted_players_file=restricted_players_file,
            debug=debug
        )

    def analyze_frames(self, frames_data: List[Dict]) -> Dict:
        """Point d'entrée principal - analyse toutes les frames"""
        if self.debug:
            print(f"🔍 WindowCollector - Analysing {len(frames_data)} frames")

        self.validated_rounds = []

        # Phase 1: Nettoyage silencieux (TextValidator en mode silencieux)
        if self.debug:
            print("🧹 Phase 1: Nettoyage OCR des frames...")
            # Temporairement désactiver debug du TextValidator
            original_debug = self.text_validator.debug
            self.text_validator.debug = False

        cleaned_frames = []
        for i, frame in enumerate(frames_data):
            cleaned_frame = self._preprocess_frame_data(frame)
            cleaned_frames.append((cleaned_frame, i))

        if self.debug:
            # Restaurer debug du TextValidator
            self.text_validator.debug = original_debug
            print(f"✅ {len(cleaned_frames)} frames nettoyées")
            print("\n🎯 Phase 2: Analyse des fenêtres de collecte...")

        # Phase 2: Analyse des fenêtres avec logs propres
        for cleaned_frame, i in cleaned_frames:
            self._process_frame_clean(cleaned_frame, i, cleaned_frames)

        # Finaliser dernière fenêtre si nécessaire
        if self.collecting and len(self.current_window) > 0:
            self._finalize_current_window()

        return {
            "rounds": self.validated_rounds,
            "stats": {
                "total_frames": len(frames_data),
                "rounds_detected": len(self.validated_rounds),
                "collection_method": "window_based"
            }
        }

    def _process_frame(self, frame: Dict, index: int, all_frames: List[Dict]):
        """Traite une frame individuelle"""
        # Nettoyer les données OCR AVANT traitement
        cleaned_frame = self._preprocess_frame_data(frame)
        timer_value = self._extract_timer(cleaned_frame)

        if timer_value is None:
            return

        # Détecter déclenchement de collecte
        if not self.collecting:
            if self._should_start_collection(timer_value, index, all_frames):
                self._start_collection(cleaned_frame, index)
        else:
            # Continuer collecte ou l'arrêter
            if self._should_stop_collection(timer_value, index, all_frames):
                self._stop_collection()
                # Redémarrer collection si on a un nouveau timer haut
                if timer_value >= self.timer_high_threshold:
                    self._start_collection(cleaned_frame, index)
            else:
                self._add_to_collection(cleaned_frame, index)

    def _process_frame_clean(self, cleaned_frame: Dict, index: int, all_cleaned_frames: List[tuple]):
        """Traite une frame déjà nettoyée - logs propres pour WindowCollector"""
        timer_value = self._extract_timer(cleaned_frame)

        if timer_value is None:
            return

        # Détecter déclenchement de collecte
        if not self.collecting:
            if self._should_start_collection_clean(timer_value, index, all_cleaned_frames):
                self._start_collection(cleaned_frame, index)
        else:
            # Continuer collecte ou l'arrêter
            if self._should_stop_collection_clean(timer_value, index, all_cleaned_frames):
                self._stop_collection()
                # Redémarrer collection si on a un nouveau timer haut
                if timer_value >= self.timer_high_threshold:
                    self._start_collection(cleaned_frame, index)
            else:
                self._add_to_collection(cleaned_frame, index)

    def _should_start_collection(self, timer_value: int, index: int, all_frames: List[Dict]) -> bool:
        """Détermine s'il faut commencer une collecte"""
        if timer_value < self.timer_high_threshold:
            return False

        # Vérifier zone tampon AVANT (gap temporel)
        if index < self.buffer_size:
            return True  # Début de vidéo

        # Regarder les frames précédentes
        has_gap = True
        for i in range(max(0, index - self.buffer_size), index):
            prev_timer = self._extract_timer(all_frames[i])
            if prev_timer is not None and prev_timer >= self.timer_high_threshold:
                has_gap = False
                break

        if self.debug and has_gap:
            print(f"🟢 TRIGGER: timer={timer_value} à frame {index}, gap confirmé")

        return has_gap

    def _should_start_collection_clean(self, timer_value: int, index: int, all_cleaned_frames: List[tuple]) -> bool:
        """Version pour frames nettoyées - détermine s'il faut commencer une collecte"""
        if timer_value < self.timer_high_threshold:
            return False

        # Vérifier zone tampon AVANT (gap temporel)
        if index < self.buffer_size:
            return True  # Début de vidéo

        # Regarder les frames précédentes
        has_gap = True
        for i in range(max(0, index - self.buffer_size), index):
            prev_frame, _ = all_cleaned_frames[i]
            prev_timer = self._extract_timer(prev_frame)
            if prev_timer is not None and prev_timer >= self.timer_high_threshold:
                has_gap = False
                break

        if self.debug and has_gap:
            # Récupérer le timestamp de la frame pour enrichir le log
            timestamp = '?'
            if index < len(all_cleaned_frames):
                frame, _ = all_cleaned_frames[index]
                timestamp = self._extract_timestamp(frame)
            print(f"🟢 TRIGGER: timer={timer_value} à frame {index} ({timestamp}), gap confirmé")

        return has_gap

    def _should_stop_collection(self, timer_value: int, index: int, all_frames: List[Dict]) -> bool:
        """Détermine s'il faut arrêter la collecte"""
        # Nouveau timer haut détecté
        if timer_value >= self.timer_high_threshold:
            # Vérifier que c'est bien un nouveau round (zone tampon APRÈS)
            if self.debug:
                print(f"🔴 STOP TRIGGER: nouveau timer haut {timer_value} à frame {index}")
            return True

        return False

    def _should_stop_collection_clean(self, timer_value: int, index: int, all_cleaned_frames: List[tuple]) -> bool:
        """Version pour frames nettoyées - détermine s'il faut arrêter la collecte"""
        if timer_value is None:
            return False

        # Ajouter le timer courant à l'historique pour lissage
        self.timer_history.append(timer_value)

        # Garder seulement les 5 derniers timers pour lissage
        if len(self.timer_history) > 5:
            self.timer_history.pop(0)

        # Calculer timer lissé (médiane pour éviter les valeurs aberrantes)
        smoothed_current = self._get_smoothed_timer()

        # Détecter un nouveau round basé sur la progression des timers
        should_stop = self._detect_new_round_from_timer_progression(smoothed_current, index, all_cleaned_frames)

        if should_stop and self.debug:
            # Récupérer le timestamp de la frame pour enrichir le log
            timestamp = '?'
            if index < len(all_cleaned_frames):
                frame, _ = all_cleaned_frames[index]
                timestamp = self._extract_timestamp(frame)
            print(f"🔴 STOP TRIGGER: nouveau round détecté, timer={timer_value} (lissé={smoothed_current}) à frame {index} ({timestamp})")

        return should_stop

    def _start_collection(self, frame: Dict, index: int):
        """Démarre une nouvelle collecte"""
        self.collecting = True
        self.current_window = [(frame, index)]

        # Enregistrer le timer de début pour comparaisons futures
        self.window_start_timer = self._extract_timer(frame)
        self.timer_history = [self.window_start_timer] if self.window_start_timer else []

        if self.debug:
            timestamp = self._extract_timestamp(frame)
            timer_value = self._extract_timer(frame)
            print(f"📥 START collecte à frame {index} ({timestamp}) - timer={timer_value}")

    def _add_to_collection(self, frame: Dict, index: int):
        """Ajoute une frame à la collecte courante"""
        self.current_window.append((frame, index))
        if self.debug and len(self.current_window) % 10 == 0:
            print(f"📥 Collecte: {len(self.current_window)} frames")

    def _stop_collection(self):
        """Arrête la collecte et valide la fenêtre"""
        if self.debug:
            print(f"📤 STOP collecte: {len(self.current_window)} frames collectées")

        self._finalize_current_window()
        self.collecting = False
        self.current_window = []

    def _finalize_current_window(self):
        """Valide et lisse la fenêtre collectée"""
        if len(self.current_window) == 0:
            return

        # Extraction des données brutes
        raw_data = {
            'timers': [],
            'char1': [],
            'char2': [],
            'player1': [],
            'player2': [],
            'timestamps': []
        }

        for frame, index in self.current_window:
            raw_data['timers'].append(self._extract_timer(frame))
            raw_data['char1'].append(frame.get('character1'))
            raw_data['char2'].append(frame.get('character2'))
            raw_data['player1'].append(frame.get('player1'))
            raw_data['player2'].append(frame.get('player2'))
            raw_data['timestamps'].append(frame.get('timestamp'))

        # Lissage des données
        smoothed = self._smooth_window_data(raw_data)

        # Validation cohérence
        coherence_score = self._calculate_coherence(smoothed)

        if coherence_score >= self.coherence_threshold:
            validated_round = {
                'start_time': smoothed['timestamps'][0],
                'end_time': smoothed['timestamps'][-1],
                'character1': smoothed['char1_final'],
                'character2': smoothed['char2_final'],
                'player1': smoothed['player1_final'],
                'player2': smoothed['player2_final'],
                'timer_start': smoothed['timers'][0],
                'timer_end': smoothed['timers'][-1],
                'frames_count': len(self.current_window),
                'coherence_score': coherence_score,
                'method': 'window_collection'
            }

            self.validated_rounds.append(validated_round)

            if self.debug:
                # Affichage enrichi avec joueurs et timestamp
                char1 = smoothed['char1_final'] or '?'
                char2 = smoothed['char2_final'] or '?'
                player1 = smoothed['player1_final'] or '?'
                player2 = smoothed['player2_final'] or '?'
                timestamp = smoothed['timestamps'][0] if smoothed['timestamps'] else '?'

                # Format: timestamp - Player1 (Character1) vs Player2 (Character2)
                match_display = f"{timestamp} - {player1} ({char1}) vs {player2} ({char2})"
                print(f"✅ Round validé: {match_display} (cohérence: {coherence_score:.2f})")
        else:
            if self.debug:
                print(f"❌ Fenêtre rejetée: cohérence {coherence_score:.2f} < {self.coherence_threshold}")

    def _smooth_window_data(self, raw_data: Dict) -> Dict:
        """Applique le lissage sur les données de la fenêtre"""
        smoothed = {}

        # Lissage par vote majoritaire pour chars et players
        for field in ['char1', 'char2', 'player1', 'player2']:
            values = [v for v in raw_data[field] if v is not None]
            if values:
                # Vote majoritaire
                from collections import Counter
                most_common = Counter(values).most_common(1)[0][0]
                smoothed[f'{field}_final'] = most_common
            else:
                smoothed[f'{field}_final'] = None

        # Lissage par interpolation pour timers
        timers = raw_data['timers']
        smoothed_timers = []
        for i, timer in enumerate(timers):
            if timer is not None:
                smoothed_timers.append(timer)
            else:
                # Interpolation simple
                if i > 0 and i < len(timers) - 1:
                    prev_timer = smoothed_timers[-1] if smoothed_timers else None
                    next_timer = None
                    for j in range(i + 1, len(timers)):
                        if timers[j] is not None:
                            next_timer = timers[j]
                            break

                    if prev_timer is not None and next_timer is not None:
                        interpolated = prev_timer - ((prev_timer - next_timer) // 2)
                        smoothed_timers.append(interpolated)
                    else:
                        smoothed_timers.append(0)  # Fallback
                else:
                    smoothed_timers.append(0)  # Bords

        smoothed['timers'] = smoothed_timers
        smoothed['timestamps'] = raw_data['timestamps']

        return smoothed

    def _calculate_coherence(self, smoothed_data: Dict) -> float:
        """Calcule un score de cohérence pour la fenêtre"""
        scores = []

        # Cohérence des timers (doit décroître)
        timers = smoothed_data['timers']
        if len(timers) >= 2:
            decreasing_count = 0
            for i in range(1, len(timers)):
                if timers[i] <= timers[i-1]:
                    decreasing_count += 1
            timer_coherence = decreasing_count / (len(timers) - 1)
            scores.append(timer_coherence)

        # Cohérence des caractères (doivent rester constants)
        char_coherence = 1.0  # Déjà lissé par vote majoritaire
        scores.append(char_coherence)

        # Score global
        return sum(scores) / len(scores) if scores else 0.0

    def _extract_timer(self, frame: Dict) -> Optional[int]:
        """Extrait la valeur du timer d'une frame"""
        timer_str = frame.get('timer_value')
        if timer_str is None:
            return None

        try:
            return int(timer_str)
        except (ValueError, TypeError):
            return None

    def _extract_timestamp(self, frame: Dict) -> str:
        """Extrait le timestamp vidéo d'une frame"""
        return frame.get('timestamp', '00:00:00')

    def _extract_players(self, frame: Dict) -> tuple:
        """Extrait les noms de joueurs d'une frame"""
        player1 = frame.get('player1', '')
        player2 = frame.get('player2', '')
        return (player1, player2)

    def _get_smoothed_timer(self) -> int:
        """
        Calcule un timer lissé à partir de l'historique pour éviter les valeurs aberrantes.
        Utilise la médiane des derniers timers.
        """
        if not self.timer_history:
            return 0

        # Filtrer les None
        valid_timers = [t for t in self.timer_history if t is not None]
        if not valid_timers:
            return 0

        # Calculer la médiane pour éviter les outliers
        sorted_timers = sorted(valid_timers)
        n = len(sorted_timers)
        if n % 2 == 0:
            return (sorted_timers[n//2 - 1] + sorted_timers[n//2]) // 2
        else:
            return sorted_timers[n//2]

    def _detect_new_round_from_timer_progression(self, current_timer: int, index: int, all_cleaned_frames: List[tuple]) -> bool:
        """
        Détecte un nouveau round basé sur la progression des timers.

        Critères pour détecter un nouveau round :
        1. Timer fait un saut vers le haut (ex: 45 → 99)
        2. Timer augmente de façon significative (ex: 72 → 95)
        3. Mais PAS si c'est une progression décroisante normale (99 → 95 → 90...)
        """
        if len(self.timer_history) < 2:
            return False  # Pas assez d'historique

        # Obtenir le timer précédent lissé
        prev_history = self.timer_history[:-1]  # Tout sauf le dernier
        if not prev_history:
            return False

        # Calculer le timer précédent lissé
        valid_prev = [t for t in prev_history if t is not None]
        if not valid_prev:
            return False

        prev_timer = valid_prev[-1]  # Le plus récent des précédents

        # Calcul du delta
        timer_delta = current_timer - prev_timer

        # Critère 1: Saut important vers le haut (nouveau round clair)
        if timer_delta >= self.timer_jump_threshold:
            return True

        # Critère 2: Timer repart à 95+ après être descendu bas
        if current_timer >= self.timer_high_threshold and prev_timer <= self.timer_low_threshold:
            return True

        # Critère 3: Progression décroissante normale → continuer
        if timer_delta <= 0:  # Timer décroit ou stable
            return False

        # Critère 4: Léger saut vers le haut mais pas assez significatif
        if 0 < timer_delta < self.timer_jump_threshold:
            return False  # Probablement juste du bruit OCR

        return False

    def _preprocess_frame_data(self, frame: Dict) -> Dict:
        """
        Nettoie les données OCR avant déduction en utilisant TextValidator.

        Corrige les erreurs OCR communes comme:
        - "DEE Jav" → "DEE JAY"
        - "RYUU" → "RYU"
        - "M.BISON " → "M. BISON"
        """
        try:
            # Utiliser validate_frame du TextValidator pour nettoyage complet
            cleaned_frame = self.text_validator.validate_frame(frame)

            # Afficher les corrections seulement si TextValidator est en mode debug
            if self.debug and self.text_validator.debug:
                # Afficher les corrections apportées
                changes = []
                for field in ['timer_value', 'character1', 'character2', 'player1', 'player2']:
                    if field in frame and field in cleaned_frame:
                        original = frame.get(field, '')
                        cleaned = cleaned_frame.get(field, '')
                        if original != cleaned and original and cleaned:
                            changes.append(f"{field}: '{original}' → '{cleaned}'")

                if changes:
                    print(f"🧹 OCR cleaned: {', '.join(changes)}")

            return cleaned_frame

        except Exception as e:
            if self.debug:
                print(f"❌ Preprocessing error: {e}")
            return frame  # Fallback vers frame originale