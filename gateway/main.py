"""Compatibility entrypoint. Prefer python -m gateway from repository root."""
if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from gateway.__main__ import main
    main()
