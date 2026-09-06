"""
reid_evaluation.py

Quantitative vehicle Re-ID evaluation system for SIH PS 26127.

Measures Re-ID performance using standard metrics:
- IDF1 (ID F1 score)
- True Positive Rate (same vehicle match accuracy)
- False Positive Rate (different vehicle false match rate)
- Appearance similarity distribution analysis

This provides quantitative evidence for Re-ID capabilities rather than
qualitative claims.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import json

try:
    from recognition.appearance import appearance_similarity
    _APPEARANCE_AVAILABLE = True
except ImportError:
    _APPEARANCE_AVAILABLE = False

def _fallback_similarity(vec_a, vec_b):
    """Fallback similarity calculation when appearance module unavailable."""
    if vec_a is None or vec_b is None:
        return 0.0
    a = np.array(vec_a)
    b = np.array(vec_b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    sim = np.dot(a, b) / (norm_a * norm_b)
    return round(max(0.0, float(sim)), 3)


@dataclass
class ReIDMetrics:
    """Complete Re-ID evaluation metrics."""
    timestamp: str
    total_pairs: int
    same_vehicle_pairs: int
    different_vehicle_pairs: int
    
    # True Positive metrics (same vehicle correctly matched)
    true_positives: int
    true_positive_rate: float
    avg_same_vehicle_similarity: float
    
    # False Positive metrics (different vehicles incorrectly matched)
    false_positives: int
    false_positive_rate: float
    avg_different_vehicle_similarity: float
    
    # IDF1 calculation
    idf1: float
    id_precision: float
    id_recall: float
    
    # Similarity threshold analysis
    optimal_threshold: float
    threshold_analysis: Dict[str, float]


class ReIDEvaluator:
    """Evaluates vehicle Re-ID performance using appearance similarity."""
    
    def __init__(self, similarity_threshold: float = 0.75):
        """
        Args:
            similarity_threshold: Threshold for considering two vehicles as same
        """
        self.similarity_threshold = similarity_threshold
        self.evaluation_data = []
    
    def add_vehicle_pair(self, 
                        appearance_a: List[float], 
                        appearance_b: List[float],
                        is_same_vehicle: bool,
                        vehicle_id_a: str = "unknown",
                        vehicle_id_b: str = "unknown"):
        """
        Add a vehicle pair for evaluation.
        
        Args:
            appearance_a: Appearance vector for first vehicle
            appearance_b: Appearance vector for second vehicle  
            is_same_vehicle: Ground truth - are these the same vehicle?
            vehicle_id_a: Identifier for first vehicle
            vehicle_id_b: Identifier for second vehicle
        """
        try:
            if _APPEARANCE_AVAILABLE:
                similarity = appearance_similarity(appearance_a, appearance_b)
            else:
                similarity = _fallback_similarity(appearance_a, appearance_b)
        except Exception:
            similarity = _fallback_similarity(appearance_a, appearance_b)
        
        self.evaluation_data.append({
            "similarity": similarity,
            "is_same_vehicle": is_same_vehicle,
            "vehicle_id_a": vehicle_id_a,
            "vehicle_id_b": vehicle_id_b,
            "predicted_same": similarity >= self.similarity_threshold
        })
    
    def evaluate(self) -> ReIDMetrics:
        """Calculate comprehensive Re-ID metrics."""
        if not self.evaluation_data:
            return self._empty_metrics()
        
        total_pairs = len(self.evaluation_data)
        same_vehicle_pairs = sum(1 for d in self.evaluation_data if d["is_same_vehicle"])
        different_vehicle_pairs = total_pairs - same_vehicle_pairs
        
        # Calculate True Positives (same vehicle correctly identified as same)
        true_positives = sum(
            1 for d in self.evaluation_data 
            if d["is_same_vehicle"] and d["predicted_same"]
        )
        
        # Calculate False Positives (different vehicles incorrectly identified as same)
        false_positives = sum(
            1 for d in self.evaluation_data 
            if not d["is_same_vehicle"] and d["predicted_same"]
        )
        
        # Calculate rates
        true_positive_rate = true_positives / same_vehicle_pairs if same_vehicle_pairs > 0 else 0.0
        false_positive_rate = false_positives / different_vehicle_pairs if different_vehicle_pairs > 0 else 0.0
        
        # Calculate average similarities
        same_vehicle_similarities = [d["similarity"] for d in self.evaluation_data if d["is_same_vehicle"]]
        different_vehicle_similarities = [d["similarity"] for d in self.evaluation_data if not d["is_same_vehicle"]]
        
        avg_same_vehicle_similarity = np.mean(same_vehicle_similarities) if same_vehicle_similarities else 0.0
        avg_different_vehicle_similarity = np.mean(different_vehicle_similarities) if different_vehicle_similarities else 0.0
        
        # Calculate IDF1 (ID F1 score)
        # IDF1 = 2 * (ID Precision * ID Recall) / (ID Precision + ID Recall)
        id_precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        id_recall = true_positive_rate  # Same as TPR for same-vehicle identification
        
        if (id_precision + id_recall) > 0:
            idf1 = 2 * (id_precision * id_recall) / (id_precision + id_recall)
        else:
            idf1 = 0.0
        
        # Find optimal threshold
        optimal_threshold = self._find_optimal_threshold()
        
        # Threshold analysis
        threshold_analysis = self._analyze_thresholds()
        
        return ReIDMetrics(
            timestamp=datetime.now().isoformat(),
            total_pairs=total_pairs,
            same_vehicle_pairs=same_vehicle_pairs,
            different_vehicle_pairs=different_vehicle_pairs,
            true_positives=true_positives,
            true_positive_rate=round(true_positive_rate, 4),
            avg_same_vehicle_similarity=round(avg_same_vehicle_similarity, 4),
            false_positives=false_positives,
            false_positive_rate=round(false_positive_rate, 4),
            avg_different_vehicle_similarity=round(avg_different_vehicle_similarity, 4),
            idf1=round(idf1, 4),
            id_precision=round(id_precision, 4),
            id_recall=round(id_recall, 4),
            optimal_threshold=round(optimal_threshold, 4),
            threshold_analysis=threshold_analysis
        )
    
    def _find_optimal_threshold(self) -> float:
        """Find the optimal similarity threshold using F1 score maximization."""
        if not self.evaluation_data:
            return 0.0
        
        thresholds = np.arange(0.0, 1.0, 0.05)
        best_f1 = 0.0
        best_threshold = self.similarity_threshold
        
        for threshold in thresholds:
            tp = sum(1 for d in self.evaluation_data if d["is_same_vehicle"] and d["similarity"] >= threshold)
            fp = sum(1 for d in self.evaluation_data if not d["is_same_vehicle"] and d["similarity"] >= threshold)
            fn = sum(1 for d in self.evaluation_data if d["is_same_vehicle"] and d["similarity"] < threshold)
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            
            if (precision + recall) > 0:
                f1 = 2 * (precision * recall) / (precision + recall)
                if f1 > best_f1:
                    best_f1 = f1
                    best_threshold = threshold
        
        return best_threshold
    
    def _analyze_thresholds(self) -> Dict[str, float]:
        """Analyze performance across different thresholds."""
        analysis = {}
        thresholds = [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9]
        
        for threshold in thresholds:
            tp = sum(1 for d in self.evaluation_data if d["is_same_vehicle"] and d["similarity"] >= threshold)
            fp = sum(1 for d in self.evaluation_data if not d["is_same_vehicle"] and d["similarity"] >= threshold)
            fn = sum(1 for d in self.evaluation_data if d["is_same_vehicle"] and d["similarity"] < threshold)
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            
            if (precision + recall) > 0:
                f1 = 2 * (precision * recall) / (precision + recall)
            else:
                f1 = 0.0
            
            analysis[f"threshold_{threshold}"] = {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4)
            }
        
        return analysis
    
    def _empty_metrics(self) -> ReIDMetrics:
        """Return empty metrics when no evaluation data available."""
        return ReIDMetrics(
            timestamp=datetime.now().isoformat(),
            total_pairs=0,
            same_vehicle_pairs=0,
            different_vehicle_pairs=0,
            true_positives=0,
            true_positive_rate=0.0,
            avg_same_vehicle_similarity=0.0,
            false_positives=0,
            false_positive_rate=0.0,
            avg_different_vehicle_similarity=0.0,
            idf1=0.0,
            id_precision=0.0,
            id_recall=0.0,
            optimal_threshold=0.0,
            threshold_analysis={}
        )
    
    def generate_report(self, output_path: Optional[str] = None) -> Dict:
        """Generate comprehensive Re-ID evaluation report."""
        metrics = self.evaluate()
        report = {
            "metrics": asdict(metrics),
            "evaluation_summary": {
                "total_evaluated_pairs": metrics.total_pairs,
                "same_vehicle_accuracy": f"{metrics.true_positive_rate * 100:.1f}%",
                "different_vehicle_false_match_rate": f"{metrics.false_positive_rate * 100:.1f}%",
                "idf1_score": f"{metrics.idf1 * 100:.1f}%",
                "optimal_threshold": metrics.optimal_threshold,
                "recommendation": self._get_recommendation(metrics)
            },
            "data_quality": {
                "appearance_module_available": _APPEARANCE_AVAILABLE,
                "similarity_threshold_used": self.similarity_threshold
            }
        }
        
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
        
        return report
    
    def _get_recommendation(self, metrics: ReIDMetrics) -> str:
        """Generate recommendation based on metrics."""
        if metrics.idf1 >= 0.85:
            return "Excellent Re-ID performance - suitable for production use"
        elif metrics.idf1 >= 0.70:
            return "Good Re-ID performance - suitable for demo with limitations"
        elif metrics.idf1 >= 0.50:
            return "Moderate Re-ID performance - requires improvement for production"
        else:
            return "Poor Re-ID performance - not suitable for production use"


def create_demo_evaluation() -> ReIDEvaluator:
    """
    Create a demo Re-ID evaluation with synthetic data.
    This demonstrates the evaluation system without requiring real vehicle crops.
    """
    evaluator = ReIDEvaluator(similarity_threshold=0.75)
    
    # Simulate same-vehicle pairs (should have high similarity)
    np.random.seed(42)
    for i in range(10):
        base_vector = np.random.normal(0, 1, 512).tolist()
        # Add very small noise to simulate same vehicle at different angles/times
        # This should result in high cosine similarity (>0.8)
        noisy_vector = [(v + np.random.normal(0, 0.05)) for v in base_vector]
        evaluator.add_vehicle_pair(
            base_vector, noisy_vector, 
            is_same_vehicle=True,
            vehicle_id_a=f"vehicle_{i}",
            vehicle_id_b=f"vehicle_{i}"
        )
    
    # Simulate different-vehicle pairs (should have low similarity)
    for i in range(15):
        # Use completely different random vectors with different seeds
        np.random.seed(i + 100)
        vector_a = np.random.normal(0, 1, 512).tolist()
        np.random.seed(i + 200)
        vector_b = np.random.normal(0, 1, 512).tolist()
        evaluator.add_vehicle_pair(
            vector_a, vector_b,
            is_same_vehicle=False,
            vehicle_id_a=f"vehicle_{i}",
            vehicle_id_b=f"vehicle_{i+100}"
        )
    
    return evaluator


if __name__ == "__main__":
    # Run demo evaluation
    print("Running Re-ID Evaluation Demo...")
    evaluator = create_demo_evaluation()
    report = evaluator.generate_report("outputs/reid_evaluation_report.json")
    
    print("\n=== Re-ID Evaluation Results ===")
    print(f"Total pairs evaluated: {report['metrics']['total_pairs']}")
    print(f"Same vehicle accuracy: {report['evaluation_summary']['same_vehicle_accuracy']}")
    print(f"Different vehicle false match rate: {report['evaluation_summary']['different_vehicle_false_match_rate']}")
    print(f"IDF1 Score: {report['evaluation_summary']['idf1_score']}")
    print(f"Optimal threshold: {report['evaluation_summary']['optimal_threshold']}")
    print(f"Recommendation: {report['evaluation_summary']['recommendation']}")
    print(f"\nReport saved to: outputs/reid_evaluation_report.json")