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


def test_provider_admin_uses_provider_scoped_availability_and_keeps_search_focus() -> None:
    assert "x.provider_model_key||`${x.provider}::${x.model_id}`" in ADMIN_HTML
    assert "freeOnlyProvider=p?.provider_id==='openrouter'||p?.provider_id==='nous'" in ADMIN_HTML
    assert "providersFilterModels(this)" in ADMIN_HTML
    assert "next.focus()" in ADMIN_HTML
