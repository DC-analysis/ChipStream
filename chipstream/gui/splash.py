try:
    # only available in PyInstaller builds
    import pyi_splash  # pyright: ignore[reportMissingModuleSource]
except (ImportError, ModuleNotFoundError):
    pyi_splash = None


def splash_close():
    """Close the splash screen"""
    if pyi_splash is not None and pyi_splash.is_alive():
        pyi_splash.close()
