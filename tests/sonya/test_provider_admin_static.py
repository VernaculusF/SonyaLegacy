from sonya.admin.static import ADMIN_HTML


def test_provider_admin_uses_pool_console_and_protected_secrets() -> None:
    assert "Provider pools" in ADMIN_HTML
    assert "Model pool" in ADMIN_HTML
    assert "Rotate secret" in ADMIN_HTML
    assert "Refresh / probe" in ADMIN_HTML
    assert "/api/providers/accounts/${id}/secret" in ADMIN_HTML
    assert "New credentials use protected provider-account secrets." in ADMIN_HTML


def test_provider_admin_does_not_render_legacy_add_key_form() -> None:
    override = ADMIN_HTML.split("renderers.providers = function(d)", 1)[1].split(
        "async function providersSaveSettings()", 1
    )[0]

    assert "<h3>Add key</h3>" not in override
    assert "providersAddKey()" not in override


def test_provider_admin_hides_stale_openrouter_manual_aliases_by_default() -> None:
    assert (
        "rawPm.filter(x=>available.has(x.model_id)||(x.is_free&&x.discovery_source!=='manual'))"
        in ADMIN_HTML
    )
