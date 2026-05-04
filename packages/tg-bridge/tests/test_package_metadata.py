from tg_bridge import __version__


def test_package_metadata_exists():
    assert __version__ == "0.1.0"
