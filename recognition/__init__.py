# Recognition module for OCR, plate matching, and evaluation
from .ocr_reader import try_init_ocr, PlateOCR, vote_plate_text
from .plate_matcher import normalize_plate, plate_similarity
from .plate_normalizer import normalize_indian_plate
from .ocr_evaluation import OCREvaluator, OCREvaluationReport, create_sample_dataset

# Optional torch-dependent imports
try:
    from .appearance import get_appearance_vector
    _torch_available = True
except (ImportError, OSError):
    # torch may fail to load on some systems (e.g., Windows DLL issues)
    get_appearance_vector = None
    _torch_available = False

__all__ = [
    'try_init_ocr', 'PlateOCR', 'vote_plate_text',
    'normalize_plate', 'plate_similarity', 
    'normalize_indian_plate',
    'get_appearance_vector',
    'OCREvaluator', 'OCREvaluationReport', 'create_sample_dataset'
]