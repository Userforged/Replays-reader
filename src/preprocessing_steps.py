"""
Définit les étapes de preprocessing disponibles pour l'OCR.
Utilise l'approche Flag/Enum pour une API élégante et type-safe.
"""

from enum import Flag, auto


class PreprocessingStep(Flag):
    """
    Énumération des étapes de preprocessing disponibles pour l'OCR.
    
    Utilise Flag pour permettre les combinaisons avec | (OR) et & (AND).
    
    Étapes individuelles:
        GRAYSCALE: Conversion en niveaux de gris
        DENOISING: Débruitage (fastNlMeansDenoising)
        NORMALIZE: Normalisation de l'histogramme
        CLAHE: Enhancement de contraste adaptatif
        THRESHOLD: Seuillage binaire (très transformant)
        MORPHOLOGY: Opérations morphologiques (très transformant)
        UPSCALE: Agrandissement 3x pour améliorer l'OCR
        
    Presets utiles:
        NONE: Aucun preprocessing (image originale)
        MINIMAL: Juste grayscale
        LIGHT: Preprocessing léger (grayscale + normalisation)
        STANDARD: Preprocessing standard pour TrOCR
        AGGRESSIVE: Preprocessing complet (toutes étapes)
        
    Exemples d'usage:
        # Aucun preprocessing
        steps = PreprocessingStep.NONE
        
        # Presets
        steps = PreprocessingStep.LIGHT
        steps = PreprocessingStep.STANDARD
        
        # Combinaisons personnalisées
        steps = PreprocessingStep.GRAYSCALE | PreprocessingStep.THRESHOLD
        
        # Modification d'un preset
        steps = PreprocessingStep.STANDARD & ~PreprocessingStep.CLAHE  # Standard sans CLAHE
        
        # Test d'inclusion
        if PreprocessingStep.GRAYSCALE in steps:
            print("Grayscale sera appliqué")
    """
    
    # Étapes individuelles
    GRAYSCALE = auto()
    DENOISING = auto()
    NORMALIZE = auto()
    CLAHE = auto()
    THRESHOLD = auto()
    MORPHOLOGY = auto()
    UPSCALE = auto()
    
    # Presets pour différents niveaux de preprocessing
    NONE = 0
    MINIMAL = GRAYSCALE
    LIGHT = GRAYSCALE | NORMALIZE
    STANDARD = GRAYSCALE | NORMALIZE | CLAHE
    AGGRESSIVE = GRAYSCALE | DENOISING | NORMALIZE | CLAHE | THRESHOLD | MORPHOLOGY | UPSCALE
    
    def __str__(self) -> str:
        """Représentation lisible de la combinaison d'étapes."""
        if self == PreprocessingStep.NONE:
            return "NONE"
        elif self == PreprocessingStep.MINIMAL:
            return "MINIMAL"
        elif self == PreprocessingStep.LIGHT:
            return "LIGHT"
        elif self == PreprocessingStep.STANDARD:
            return "STANDARD"
        elif self == PreprocessingStep.AGGRESSIVE:
            return "AGGRESSIVE"
        else:
            # Combinaison personnalisée
            active_steps = []
            if PreprocessingStep.GRAYSCALE in self:
                active_steps.append("GRAYSCALE")
            if PreprocessingStep.DENOISING in self:
                active_steps.append("DENOISING")
            if PreprocessingStep.NORMALIZE in self:
                active_steps.append("NORMALIZE")
            if PreprocessingStep.CLAHE in self:
                active_steps.append("CLAHE")
            if PreprocessingStep.THRESHOLD in self:
                active_steps.append("THRESHOLD")
            if PreprocessingStep.MORPHOLOGY in self:
                active_steps.append("MORPHOLOGY")
            if PreprocessingStep.UPSCALE in self:
                active_steps.append("UPSCALE")
            return " | ".join(active_steps) if active_steps else "NONE"
    
    def get_step_names(self) -> list[str]:
        """Retourne la liste des noms d'étapes actives."""
        steps = []
        if PreprocessingStep.GRAYSCALE in self:
            steps.append("Conversion en niveaux de gris")
        if PreprocessingStep.DENOISING in self:
            steps.append("Débruitage")
        if PreprocessingStep.NORMALIZE in self:
            steps.append("Normalisation de l'histogramme")
        if PreprocessingStep.CLAHE in self:
            steps.append("Enhancement CLAHE")
        if PreprocessingStep.THRESHOLD in self:
            steps.append("Seuillage binaire")
        if PreprocessingStep.MORPHOLOGY in self:
            steps.append("Opérations morphologiques")
        if PreprocessingStep.UPSCALE in self:
            steps.append("Upscaling final")
        return steps