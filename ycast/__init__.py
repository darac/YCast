try:
    import importlib.metadata as importlib_metadata
except ModuleNotFoundError:
    import importlib_metadata  # type: ignore

# Read the version from the packaging data (pyproject.toml / setup.py / etc)
__version__ = importlib_metadata.version(__name__)
