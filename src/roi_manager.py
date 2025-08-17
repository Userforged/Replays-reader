"""
RoiManager - Gestionnaire centralisé pour les ROIs (Regions of Interest)

Cette classe centralise toute la logique de gestion des ROIs pour les notebooks
ROIs_placer et test-analyze, en gérant le fichier rois_config.json.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

import cv2 as cv
import numpy as np


class RoiManager:
    """
    Gestionnaire centralisé pour les ROIs (Regions of Interest).

    Fonctionnalités:
    - Chargement/sauvegarde depuis rois_config.json
    - Accès aux ROIs individuelles ou en groupe
    - Modification et validation des ROIs
    - Conversion entre formats (JSON <-> ImageAnalyzer)
    - Validation et vérification des ROIs
    - Prévisualisation sur images
    """

    def __init__(self, config_file: str = "rois_config.json"):
        """
        Initialise le RoiManager.

        Args:
            config_file: Chemin vers le fichier de configuration JSON
        """
        self.config_file = config_file
        self._config = None
        self._loaded = False

    def load(self) -> None:
        """
        Charge la configuration depuis le fichier JSON.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas
            ValueError: Si le JSON est invalide
            RuntimeError: Pour autres erreurs de chargement
        """
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                self._config = json.load(f)

            # Validation de base
            if "rois" not in self._config:
                raise ValueError(f"Clé 'rois' manquante dans {self.config_file}")

            self._loaded = True

        except FileNotFoundError:
            raise FileNotFoundError(
                f"Fichier de configuration non trouvé: {self.config_file}\n"
                f"Assurez-vous que le fichier existe et est accessible"
            )
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Erreur JSON dans {self.config_file}: {e}\n"
                f"Vérifiez la syntaxe du fichier JSON"
            )
        except Exception as e:
            raise RuntimeError(f"Erreur lors du chargement de {self.config_file}: {e}")

    def save(self) -> None:
        """
        Sauvegarde la configuration dans le fichier JSON.

        Raises:
            RuntimeError: Si pas de configuration chargée ou erreur de sauvegarde
        """
        if not self._loaded or self._config is None:
            raise RuntimeError("Aucune configuration chargée. Utilisez load() d'abord.")

        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise RuntimeError(f"Erreur lors de la sauvegarde: {e}")

    def get_roi(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Récupère une ROI par son nom.

        Args:
            name: Nom de la ROI ('timer', 'character1', 'character2')

        Returns:
            Dict avec la configuration de la ROI ou None si non trouvée
        """
        if not self._loaded:
            raise RuntimeError("Configuration non chargée. Utilisez load() d'abord.")

        for roi in self._config["rois"]:
            if roi["name"] == name:
                return (
                    roi.copy()
                )  # Retourner une copie pour éviter les modifications accidentelles
        return None

    def get_all_rois(self) -> List[Dict[str, Any]]:
        """
        Récupère toutes les ROIs.

        Returns:
            Liste des ROIs avec leurs configurations
        """
        if not self._loaded:
            raise RuntimeError("Configuration non chargée. Utilisez load() d'abord.")

        return [roi.copy() for roi in self._config["rois"]]

    def set_roi(self, name: str, roi_config: Dict[str, Any]) -> None:
        """
        Met à jour ou ajoute une ROI.

        Args:
            name: Nom de la ROI
            roi_config: Configuration complète de la ROI
        """
        if not self._loaded:
            raise RuntimeError("Configuration non chargée. Utilisez load() d'abord.")

        # Valider la configuration
        self._validate_roi_config(roi_config)

        # Mettre à jour si existe, sinon ajouter
        for i, roi in enumerate(self._config["rois"]):
            if roi["name"] == name:
                self._config["rois"][i] = roi_config.copy()
                return

        # Ajouter nouvelle ROI
        self._config["rois"].append(roi_config.copy())

    def update_roi_boundaries(self, name: str, boundaries: Dict[str, float]) -> None:
        """
        Met à jour seulement les boundaries d'une ROI existante.

        Args:
            name: Nom de la ROI
            boundaries: Dict avec left, top, right, bottom en pourcentages
        """
        roi = self.get_roi(name)
        if roi is None:
            raise ValueError(f"ROI '{name}' non trouvée")

        # Valider les boundaries
        required_keys = ["left", "top", "right", "bottom"]
        for key in required_keys:
            if key not in boundaries:
                raise ValueError(f"Clé '{key}' manquante dans boundaries")
            if not 0 <= boundaries[key] <= 1:
                raise ValueError(f"Valeur '{key}' doit être entre 0 et 1")

        if boundaries["left"] >= boundaries["right"]:
            raise ValueError("left doit être < right")
        if boundaries["top"] >= boundaries["bottom"]:
            raise ValueError("top doit être < bottom")

        # Mettre à jour
        roi["boundaries"].update(boundaries)
        self.set_roi(name, roi)

    def get_roi_names(self) -> List[str]:
        """
        Récupère la liste des noms de ROIs disponibles.

        Returns:
            Liste des noms de ROIs
        """
        if not self._loaded:
            raise RuntimeError("Configuration non chargée. Utilisez load() d'abord.")

        return [roi["name"] for roi in self._config["rois"]]

    def has_roi(self, name: str) -> bool:
        """
        Vérifie si une ROI existe.

        Args:
            name: Nom de la ROI

        Returns:
            True si la ROI existe
        """
        return name in self.get_roi_names()

    def to_image_analyzer_format(self) -> Dict[str, Dict[str, float]]:
        """
        Convertit les ROIs au format attendu par ImageAnalyzer.

        Returns:
            Dict avec les ROIs au format {nom: {left, top, right, bottom}}
        """
        if not self._loaded:
            raise RuntimeError("Configuration non chargée. Utilisez load() d'abord.")

        result = {}
        for roi in self._config["rois"]:
            name = roi["name"]
            boundaries = roi["boundaries"]
            result[name] = {
                "left": boundaries["left"],
                "top": boundaries["top"],
                "right": boundaries["right"],
                "bottom": boundaries["bottom"],
            }

        return result

    def get_roi_for_image_analyzer(self, name: str) -> Optional[Dict[str, float]]:
        """
        Récupère une ROI au format ImageAnalyzer.

        Args:
            name: Nom de la ROI

        Returns:
            Dict avec {left, top, right, bottom} ou None
        """
        roi = self.get_roi(name)
        if roi is None:
            return None

        return {
            "left": roi["boundaries"]["left"],
            "top": roi["boundaries"]["top"],
            "right": roi["boundaries"]["right"],
            "bottom": roi["boundaries"]["bottom"],
        }

    def validate_all_rois(self) -> Tuple[bool, List[str]]:
        """
        Valide toutes les ROIs.

        Returns:
            Tuple (toutes_valides, liste_erreurs)
        """
        if not self._loaded:
            raise RuntimeError("Configuration non chargée. Utilisez load() d'abord.")

        errors = []

        for roi in self._config["rois"]:
            try:
                self._validate_roi_config(roi)
            except ValueError as e:
                errors.append(f"ROI '{roi.get('name', 'unknown')}': {e}")

        return len(errors) == 0, errors

    def get_roi_info_summary(self) -> str:
        """
        Génère un résumé textuel des ROIs configurées.

        Returns:
            Chaîne de caractères avec le résumé
        """
        if not self._loaded:
            return "Configuration non chargée"

        lines = [f"Configuration: {self.config_file}"]
        lines.append(f"ROIs disponibles: {len(self._config['rois'])}")

        for roi in self._config["rois"]:
            name = roi["name"]
            boundaries = roi["boundaries"]
            label = roi.get("label", name.upper())
            roi_type = roi.get("type", "ocr")

            lines.append(
                f"  - {label} ({name}): "
                f"{boundaries['left']:.3f},{boundaries['top']:.3f} → "
                f"{boundaries['right']:.3f},{boundaries['bottom']:.3f} "
                f"[{roi_type}]"
            )

        return "\n".join(lines)

    def preview_rois_on_image(
        self, image: np.ndarray, show_labels: bool = True
    ) -> np.ndarray:
        """
        Dessine les ROIs sur une image pour prévisualisation.

        Args:
            image: Image OpenCV (numpy array)
            show_labels: Afficher les labels des ROIs

        Returns:
            Image avec les ROIs dessinées
        """
        if not self._loaded:
            raise RuntimeError("Configuration non chargée. Utilisez load() d'abord.")

        preview_img = image.copy()
        height, width = image.shape[:2]

        for roi in self._config["rois"]:
            name = roi["name"]
            boundaries = roi["boundaries"]
            color = tuple(boundaries.get("color", [0, 255, 0]))  # Vert par défaut
            label = roi.get("label", name.upper())

            # Calculer les coordonnées en pixels
            left = int(boundaries["left"] * width)
            top = int(boundaries["top"] * height)
            right = int(boundaries["right"] * width)
            bottom = int(boundaries["bottom"] * height)

            # Dessiner le rectangle
            cv.rectangle(preview_img, (left, top), (right, bottom), color, 2)

            if show_labels:
                # Ajouter le label
                font = cv.FONT_HERSHEY_SIMPLEX
                scale = 0.6
                thickness = 2
                (text_width, text_height), _ = cv.getTextSize(
                    label, font, scale, thickness
                )
                text_x = left
                text_y = max(top - 10, text_height + 5)

                # Fond noir pour le texte
                cv.rectangle(
                    preview_img,
                    (text_x - 2, text_y - text_height - 2),
                    (text_x + text_width + 2, text_y + 2),
                    (0, 0, 0),
                    -1,
                )

                cv.putText(
                    preview_img,
                    label,
                    (text_x, text_y),
                    font,
                    scale,
                    (255, 255, 255),
                    thickness,
                )

        return preview_img

    def get_required_roi_names(self) -> List[str]:
        """
        Retourne la liste des ROIs requises pour l'analyse.

        Returns:
            Liste des noms de ROIs requis
        """
        return ["timer", "character1", "character2"]

    def check_completeness(self) -> Tuple[bool, List[str]]:
        """
        Vérifie si toutes les ROIs requises sont configurées.

        Returns:
            Tuple (complet, liste_manquantes)
        """
        if not self._loaded:
            raise RuntimeError("Configuration non chargée. Utilisez load() d'abord.")

        required = set(self.get_required_roi_names())
        available = set(self.get_roi_names())
        missing = list(required - available)

        return len(missing) == 0, missing

    def _validate_roi_config(self, roi_config: Dict[str, Any]) -> None:
        """
        Valide la configuration d'une ROI.

        Args:
            roi_config: Configuration de la ROI à valider

        Raises:
            ValueError: Si la configuration est invalide
        """
        required_keys = ["name", "boundaries"]
        for key in required_keys:
            if key not in roi_config:
                raise ValueError(f"Clé '{key}' manquante")

        boundaries = roi_config["boundaries"]
        required_boundary_keys = ["left", "top", "right", "bottom"]

        for key in required_boundary_keys:
            if key not in boundaries:
                raise ValueError(f"Clé '{key}' manquante dans boundaries")

            value = boundaries[key]
            if not isinstance(value, (int, float)):
                raise ValueError(f"Valeur '{key}' doit être numérique")
            if not 0 <= value <= 1:
                raise ValueError(f"Valeur '{key}' doit être entre 0 et 1")

        if boundaries["left"] >= boundaries["right"]:
            raise ValueError("left doit être < right")
        if boundaries["top"] >= boundaries["bottom"]:
            raise ValueError("top doit être < bottom")

    @classmethod
    def create_from_scratch(
        cls, config_file: str, default_rois: Optional[List[Dict]] = None
    ) -> "RoiManager":
        """
        Crée un nouveau RoiManager avec une configuration par défaut.

        Args:
            config_file: Chemin du fichier de configuration
            default_rois: ROIs par défaut (optionnel)

        Returns:
            Instance de RoiManager avec configuration par défaut
        """
        if default_rois is None:
            default_rois = [
                {
                    "name": "timer",
                    "label": "TIMER",
                    "type": "ocr",
                    "boundaries": {
                        "color": [0, 255, 0],
                        "top": 0.04,
                        "bottom": 0.11,
                        "left": 0.46,
                        "right": 0.54,
                    },
                },
                {
                    "name": "character1",
                    "label": "PLAYER 1",
                    "type": "ocr",
                    "boundaries": {
                        "color": [255, 0, 0],
                        "top": 0.85,
                        "bottom": 0.95,
                        "left": 0.05,
                        "right": 0.25,
                    },
                },
                {
                    "name": "character2",
                    "label": "PLAYER 2",
                    "type": "ocr",
                    "boundaries": {
                        "color": [0, 0, 255],
                        "top": 0.85,
                        "bottom": 0.95,
                        "left": 0.75,
                        "right": 0.95,
                    },
                },
            ]

        config = {
            "_comment": "Colors are stored in BGR format (Blue, Green, Red) as used by OpenCV",
            "rois": default_rois,
        }

        # Sauvegarder le fichier
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # Créer et charger l'instance
        manager = cls(config_file)
        manager.load()
        return manager
