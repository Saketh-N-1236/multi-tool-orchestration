"""Script to check MLflow installation and configuration status."""

import sys
import importlib.util
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def check_mlflow_status():
    """Check MLflow installation and configuration."""
    print("=" * 60)
    print("MLflow Status Check")
    print("=" * 60)
    
    # Check 1: MLflow package installation
    print("\n[1] Checking MLflow package installation...")
    try:
        # Temporarily remove local mlflow from path to avoid circular import
        import sys
        if 'mlflow' in sys.modules:
            # Check if it's our local module
            mlflow_module = sys.modules['mlflow']
            if hasattr(mlflow_module, '__file__') and mlflow_module.__file__:
                if 'backend' in str(mlflow_module.__file__):
                    del sys.modules['mlflow']
                    if 'mlflow.tracking' in sys.modules:
                        del sys.modules['mlflow.tracking']
        
        import mlflow
        print(f"   [OK] MLflow is installed (version: {mlflow.__version__})")
        mlflow_installed = True
    except ImportError:
        print("   [FAIL] MLflow is NOT installed")
        print("   -> Install with: pip install mlflow>=2.8.0")
        mlflow_installed = False
        return
    
    # Check 2: MlflowClient availability
    print("\n[2] Checking MlflowClient availability...")
    try:
        from mlflow.tracking import MlflowClient
        print("   [OK] MlflowClient is available")
        client_available = True
    except (ImportError, AttributeError) as e:
        print(f"   [FAIL] MlflowClient is NOT available: {e}")
        client_available = False
        return
    
    # Check 3: Local MLflow tracker module
    print("\n[3] Checking local MLflow tracker module...")
    try:
        # Import from our local module (not the installed mlflow package)
        import importlib
        import sys
        from pathlib import Path
        
        # Import our local tracking module
        tracking_path = backend_dir / "mlflow" / "tracking.py"
        spec = importlib.util.spec_from_file_location("mlflow_tracking_local", tracking_path)
        tracking_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tracking_module)
        
        get_tracker = tracking_module.get_tracker
        MLflowTracker = tracking_module.MLflowTracker
        
        print("   [OK] Local MLflow tracker module is accessible")
        tracker_module_ok = True
    except Exception as e:
        print(f"   [FAIL] Local MLflow tracker module error: {e}")
        tracker_module_ok = False
        return
    
    # Check 4: Tracker initialization
    print("\n[4] Checking tracker initialization...")
    try:
        tracker = get_tracker()
        print(f"   [OK] Tracker initialized")
        print(f"   - Enabled: {tracker.enabled}")
        print(f"   - Tracking URI: {tracker.tracking_uri}")
        print(f"   - Experiment Name: {tracker.experiment_name}")
        tracker_ok = tracker.enabled
    except Exception as e:
        print(f"   [FAIL] Tracker initialization failed: {e}")
        import traceback
        traceback.print_exc()
        tracker_ok = False
    
    # Check 5: MLflow server connection
    print("\n[5] Checking MLflow server connection...")
    if tracker_ok:
        try:
            import mlflow
            mlflow.set_tracking_uri(tracker.tracking_uri)
            # Try to list experiments
            try:
                experiments = mlflow.search_experiments()
                print(f"   [OK] Connected to MLflow server at {tracker.tracking_uri}")
                print(f"   - Found {len(experiments)} experiments")
                
                # Check if our experiment exists
                experiment = mlflow.get_experiment_by_name(tracker.experiment_name)
                if experiment:
                    print(f"   [OK] Experiment '{tracker.experiment_name}' exists (ID: {experiment.experiment_id})")
                else:
                    print(f"   [WARN] Experiment '{tracker.experiment_name}' does not exist (will be created on first run)")
            except Exception as e:
                print(f"   [FAIL] Cannot connect to MLflow server: {e}")
                print(f"   -> Make sure MLflow server is running:")
                print(f"      mlflow ui --port 5000")
        except Exception as e:
            print(f"   [FAIL] Connection check failed: {e}")
    else:
        print("   [SKIP] Skipping connection check (tracker not enabled)")
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if mlflow_installed and client_available and tracker_ok:
        print("[OK] MLflow is ENABLED and ready to use")
        print("\nTo start MLflow UI:")
        print("  mlflow ui --port 5000")
        print("\nThen access it at: http://localhost:5000")
    else:
        print("[FAIL] MLflow is DISABLED")
        print("\nTo enable MLflow:")
        print("  1. Install MLflow: pip install mlflow>=2.8.0")
        print("  2. Start MLflow server: mlflow ui --port 5000")
        print("  3. Restart the API server")
    
    print("=" * 60)


if __name__ == "__main__":
    check_mlflow_status()
