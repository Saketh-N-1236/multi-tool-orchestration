"""Script to start MLflow UI server."""

import subprocess
import sys
import os
from pathlib import Path

def start_mlflow_ui(port: int = 5000, backend_uri: str = None):
    """Start MLflow UI server.
    
    Args:
        port: Port to run MLflow UI on (default: 5000)
        backend_uri: Backend store URI (optional, defaults to local file system)
    """
    print("=" * 70)
    print("Starting MLflow UI")
    print("=" * 70)
    
    # Check if MLflow is installed
    # IMPORTANT: Remove local backend/mlflow from path to avoid shadowing installed package
    backend_dir = Path(__file__).parent.parent
    if str(backend_dir) in sys.path:
        sys.path.remove(str(backend_dir))
    
    # Also remove any cached mlflow modules that might be from local directory
    modules_to_remove = []
    for k in sys.modules.keys():
        if k.startswith('mlflow'):
            mod = sys.modules[k]
            if hasattr(mod, '__file__') and mod.__file__:
                if 'backend' in str(mod.__file__):
                    modules_to_remove.append(k)
    for mod in modules_to_remove:
        del sys.modules[mod]
    
    try:
        # Import from installed package, not local directory
        import importlib.util
        import site
        
        # Find mlflow in site-packages
        mlflow_found = False
        for site_package in site.getsitepackages():
            mlflow_path = Path(site_package) / 'mlflow' / '__init__.py'
            if mlflow_path.exists():
                # Import using importlib to ensure we get the installed version
                spec = importlib.util.spec_from_file_location('mlflow_installed', mlflow_path)
                mlflow_installed = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mlflow_installed)
                sys.modules['mlflow'] = mlflow_installed
                mlflow = mlflow_installed
                mlflow_found = True
                break
        
        if not mlflow_found:
            # Fallback to regular import
            import mlflow
        
        version = getattr(mlflow, '__version__', 'unknown')
        print(f"[OK] MLflow is installed (version: {version})")
    except ImportError:
        print("[FAIL] MLflow is not installed")
        print("\nInstall MLflow with:")
        print("  pip install mlflow>=2.8.0")
        sys.exit(1)
    except Exception as e:
        print(f"[WARN] Could not verify MLflow version: {e}")
        print("[INFO] Proceeding with MLflow UI startup...")
    
    # Use python -m mlflow ui instead of mlflow ui to avoid mlflow.server import issues
    # IMPORTANT: Run from project root to avoid local backend/mlflow shadowing installed package
    project_root = backend_dir.parent
    original_cwd = os.getcwd()
    
    # Change to project root to avoid local mlflow module conflict
    os.chdir(project_root)
    
    # Set PYTHONPATH to exclude backend directory
    env = os.environ.copy()
    pythonpath = env.get('PYTHONPATH', '')
    if pythonpath:
        # Remove backend from PYTHONPATH if present
        paths = [p for p in pythonpath.split(os.pathsep) if 'backend' not in p]
        env['PYTHONPATH'] = os.pathsep.join(paths)
    else:
        # Ensure backend is NOT in PYTHONPATH
        env.pop('PYTHONPATH', None)
    
    cmd = [sys.executable, "-m", "mlflow", "ui", "--port", str(port), "--host", "0.0.0.0"]
    
    if backend_uri:
        cmd.extend(["--backend-store-uri", backend_uri])
    else:
        # Use default local file system backend
        # MLflow will create mlruns/ directory in current working directory (project root)
        mlruns_dir = project_root / "mlruns"
        if not mlruns_dir.exists():
            mlruns_dir.mkdir(parents=True, exist_ok=True)
            print(f"[INFO] Created MLflow runs directory: {mlruns_dir}")
    
    print(f"\nStarting MLflow UI on port {port}...")
    print(f"Access at: http://localhost:{port}")
    print(f"Working directory: {project_root}")
    print(f"\nPress Ctrl+C to stop the server")
    print("=" * 70)
    
    try:
        # Start MLflow UI using python -m mlflow ui (more reliable)
        # Run with modified environment to avoid local mlflow conflict
        subprocess.run(cmd, check=True, env=env)
    except KeyboardInterrupt:
        print("\n\n[INFO] MLflow UI stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\n[FAIL] Failed to start MLflow UI: {e}")
        print("\nTrying alternative method...")
        # Fallback: Try direct import method
        try:
            _start_mlflow_ui_direct(port, backend_uri)
        except Exception as fallback_error:
            print(f"\n[FAIL] Fallback method also failed: {fallback_error}")
            print("\nTroubleshooting:")
            print("1. Verify MLflow installation: pip show mlflow")
            print("2. Try: python -m mlflow ui --port 5000")
            print("3. Check MLflow version compatibility")
            sys.exit(1)
    except FileNotFoundError:
        print("\n[FAIL] Python executable not found")
        print("Make sure Python is installed and in PATH")
        sys.exit(1)
    finally:
        # Restore original working directory
        os.chdir(original_cwd)


def _start_mlflow_ui_direct(port: int, backend_uri: str = None):
    """Alternative method: Start MLflow UI by directly importing and running it.
    
    This is a fallback when the CLI command fails.
    """
    # Ensure we're using installed mlflow, not local
    backend_dir = Path(__file__).parent.parent
    if str(backend_dir) in sys.path:
        sys.path.remove(str(backend_dir))
    
    modules_to_remove = [k for k in sys.modules.keys() if k.startswith('mlflow')]
    for mod in modules_to_remove:
        del sys.modules[mod]
    
    try:
        # Try to import from installed package
        import importlib
        import site
        
        mlflow = None
        for site_package in site.getsitepackages():
            mlflow_path = Path(site_package) / 'mlflow' / '__init__.py'
            if mlflow_path.exists():
                mlflow = importlib.import_module('mlflow')
                # Force reload to ensure we get installed version
                importlib.reload(mlflow)
                break
        
        if mlflow is None:
            import mlflow
        
        # Try mlflow.server first (newer versions)
        try:
            from mlflow.server import app as mlflow_app
            from waitress import serve
            
            if backend_uri:
                mlflow.set_tracking_uri(backend_uri)
            
            print(f"[INFO] Starting MLflow UI using direct import method...")
            serve(mlflow_app, host="0.0.0.0", port=port)
            return
        except ImportError:
            pass
        
        # Fallback: Use mlflow.cli
        import mlflow.cli
        sys.argv = ["mlflow", "ui", "--port", str(port), "--host", "0.0.0.0"]
        if backend_uri:
            sys.argv.extend(["--backend-store-uri", backend_uri])
        mlflow.cli.main()
    except Exception as e:
        raise RuntimeError(f"Failed to start MLflow UI: {e}") from e

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Start MLflow UI server")
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to run MLflow UI on (default: 5000)"
    )
    parser.add_argument(
        "--backend-uri",
        type=str,
        default=None,
        help="Backend store URI (optional)"
    )
    
    args = parser.parse_args()
    start_mlflow_ui(port=args.port, backend_uri=args.backend_uri)
