"""
Validation script to check the Neuro-Symbolic ARC Solver installation.
Run: python validate_setup.py
"""

import sys
import importlib
from pathlib import Path


def check_python_version():
    """Check Python version."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print("✓ Python version 3.10+ OK")
        return True
    else:
        print(f"✗ Python version {version.major}.{version.minor} < 3.10 required")
        return False


def check_dependencies():
    """Check required dependencies."""
    required = ["numpy", "pydantic", "tenacity"]
    optional = ["anthropic"]

    all_ok = True

    print("\n--- Required Dependencies ---")
    for package in required:
        try:
            mod = importlib.import_module(package)
            version = getattr(mod, "__version__", "unknown")
            print(f"✓ {package} ({version})")
        except ImportError:
            print(f"✗ {package} NOT INSTALLED")
            print(f"  Install with: pip install {package}")
            all_ok = False

    print("\n--- Optional Dependencies ---")
    for package in optional:
        try:
            mod = importlib.import_module(package)
            version = getattr(mod, "__version__", "unknown")
            print(f"✓ {package} ({version})")
        except ImportError:
            print(f"○ {package} not installed (optional, for API integration)")

    return all_ok


def check_project_structure():
    """Check project file structure."""
    required_files = [
        "config.py",
        "prompts.py",
        "sandbox.py",
        "agent.py",
        "main.py",
        "utils.py",
        "__init__.py",
        "requirements.txt",
        "README.md",
        "ARCHITECTURE.md",
        "QUICKSTART.md",
    ]

    print("\n--- Project Structure ---")
    all_ok = True

    for filename in required_files:
        path = Path(filename)
        if path.exists():
            size = path.stat().st_size
            print(f"✓ {filename} ({size} bytes)")
        else:
            print(f"✗ {filename} MISSING")
            all_ok = False

    return all_ok


def check_imports():
    """Check that all modules can be imported."""
    print("\n--- Module Imports ---")
    modules = [
        "config",
        "prompts",
        "sandbox",
        "agent",
        "utils",
        "examples",
    ]

    all_ok = True
    for module_name in modules:
        try:
            importlib.import_module(module_name)
            print(f"✓ {module_name}")
        except Exception as e:
            print(f"✗ {module_name}: {e}")
            all_ok = False

    return all_ok


def check_configuration():
    """Check configuration."""
    print("\n--- Configuration ---")
    try:
        from config import config

        print(f"✓ Config loaded")
        print(f"  Model ID: {config.MODEL_ID}")
        print(f"  Max retries: {config.MAX_RETRIES}")
        print(f"  Sandbox timeout: {config.SANDBOX_TIMEOUT}s")

        if not config.API_KEY or config.API_KEY == "":
            print(f"○ API_KEY not set (required for real solving)")
        else:
            print(f"✓ API_KEY configured")

        return True
    except Exception as e:
        print(f"✗ Config error: {e}")
        return False


def check_sandbox():
    """Test sandbox execution."""
    print("\n--- Sandbox Testing ---")
    try:
        from sandbox import run_verification
        import numpy as np

        # Test simple code
        code = """
import numpy as np

def transform(grid):
    return grid
"""
        train_pairs = [{"input": [[1, 2], [3, 4]], "output": [[1, 2], [3, 4]]}]

        success, error = run_verification(code, train_pairs)

        if success:
            print("✓ Sandbox execution OK")
            return True
        else:
            print(f"✗ Sandbox test failed: {error}")
            return False
    except Exception as e:
        print(f"✗ Sandbox error: {e}")
        return False


def main():
    """Run all checks."""
    print("=" * 70)
    print("NEURO-SYMBOLIC ARC SOLVER - SETUP VALIDATION")
    print("=" * 70)

    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Project Structure", check_project_structure),
        ("Module Imports", check_imports),
        ("Configuration", check_configuration),
        ("Sandbox", check_sandbox),
    ]

    results = {}
    for name, check_func in checks:
        try:
            result = check_func()
            results[name] = result
        except Exception as e:
            print(f"\n✗ {name} check failed with exception: {e}")
            results[name] = False

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nResult: {passed}/{total} checks passed")

    if passed == total:
        print("\n🎉 All checks passed! You're ready to solve ARC tasks.")
        print("\nNext steps:")
        print("1. Read QUICKSTART.md")
        print("2. Run: python examples.py")
        print("3. Run: python main.py example_task_identity.json")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix issues above.")
        print("See QUICKSTART.md for troubleshooting.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
