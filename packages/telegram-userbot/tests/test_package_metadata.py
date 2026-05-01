from importlib.metadata import version


def test_package_metadata_exists():
    assert version("telegram-userbot") == "0.1.0"
