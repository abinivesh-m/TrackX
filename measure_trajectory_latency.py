"""
Trajectory Latency Measurement System
Measures actual end-to-end latency from observation creation to trajectory display.
"""

import time
import json
from datetime import datetime
from pathlib import Path
from database.observation_store import ObservationStore
from intelligence.trajectory import build_trajectories

class TrajectoryLatencyMeasurer:
    def __init__(self):
        self.measurements = []
        self.store = ObservationStore()
    
    def measure_trajectory_latency(self):
        """Measure trajectory computation latency with realistic data."""
        print("Measuring trajectory latency...")
        
        # Load observations
        start_load = time.time()
        observations = self.store.all_observations()
        load_time = time.time() - start_load
        
        print(f"Loaded {len(observations)} observations in {load_time:.3f}s")
        
        if len(observations) == 0:
            print("No observations to measure trajectory latency")
            return {"error": "no_observations"}
        
        # Measure trajectory building
        start_trajectory = time.time()
        trajectories = build_trajectories(observations)
        trajectory_time = time.time() - start_trajectory
        
        print(f"Built {len(trajectories)} trajectories in {trajectory_time:.3f}s")
        
        # Calculate per-observation latency
        per_obs_latency = trajectory_time / len(observations) if observations else 0
        
        measurement = {
            "timestamp": datetime.now().isoformat(),
            "observation_count": len(observations),
            "trajectory_count": len(trajectories),
            "load_time_seconds": round(load_time, 3),
            "trajectory_time_seconds": round(trajectory_time, 3),
            "per_observation_latency_ms": round(per_obs_latency * 1000, 2),
            "total_latency_seconds": round(load_time + trajectory_time, 3)
        }
        
        self.measurements.append(measurement)
        
        print(f"\nTrajectory Latency Results:")
        print(f"  Total observations: {measurement['observation_count']}")
        print(f"  Trajectories built: {measurement['trajectory_count']}")
        print(f"  Database load time: {measurement['load_time_seconds']}s")
        print(f"  Trajectory compute time: {measurement['trajectory_time_seconds']}s")
        print(f"  Per-observation latency: {measurement['per_observation_latency_ms']}ms")
        print(f"  Total end-to-end latency: {measurement['total_latency_seconds']}s")
        
        # Compare with previous 780s issue
        if measurement['total_latency_seconds'] > 100:
            print(f"\nWARNING: High latency detected ({measurement['total_latency_seconds']}s)")
        else:
            print(f"\nGood latency: {measurement['total_latency_seconds']}s (well below previous 780s issue)")
        
        return measurement
    
    def measure_multiple_runs(self, runs=3):
        """Measure trajectory latency over multiple runs for consistency."""
        print(f"\nRunning {runs} trajectory latency measurements...")
        
        results = []
        for i in range(runs):
            print(f"\n--- Run {i+1}/{runs} ---")
            result = self.measure_trajectory_latency()
            if "error" not in result:
                results.append(result)
            time.sleep(1)  # Brief pause between runs
        
        if results:
            # Calculate statistics
            latencies = [r['total_latency_seconds'] for r in results]
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            
            print(f"\n=== Multi-Run Statistics ===")
            print(f"  Average latency: {avg_latency:.3f}s")
            print(f"  Min latency: {min_latency:.3f}s")
            print(f"  Max latency: {max_latency:.3f}s")
            print(f"  Consistency: {max_latency - min_latency:.3f}s variance")
            
            return {
                "runs": len(results),
                "average_latency_seconds": round(avg_latency, 3),
                "min_latency_seconds": round(min_latency, 3),
                "max_latency_seconds": round(max_latency, 3),
                "variance_seconds": round(max_latency - min_latency, 3),
                "all_measurements": results
            }
        
        return {"error": "no_valid_measurements"}
    
    def save_measurements(self, output_file="trajectory_latency_report.json"):
        """Save latency measurements to file."""
        report = {
            "measurement_timestamp": datetime.now().isoformat(),
            "summary": self.measure_multiple_runs(3) if len(self.measurements) >= 3 else 
                     (self.measurements[0] if self.measurements else {"error": "no_measurements"}),
            "individual_measurements": self.measurements
        }
        
        output_path = Path(output_file)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nLatency report saved to: {output_path}")
        return output_path

def main():
    measurer = TrajectoryLatencyMeasurer()
    
    print("=" * 60)
    print("TRAJECTORY LATENCY MEASUREMENT")
    print("=" * 60)
    
    # Run multi-run measurement
    results = measurer.measure_multiple_runs(runs=3)
    
    # Save report
    measurer.save_measurements("trajectory_latency_report.json")
    
    print("\n" + "=" * 60)
    print("LATENCY MEASUREMENT COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()