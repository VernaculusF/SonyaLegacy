### УДАЛИТЬ ПЕРЕД ЗАПУСКОМ: This is a one-time import script. After running, delete this file and remove from git.

"""One-time import: pull provider keys from OmniRoute storage.sqlite into our own pool.

OmniRoute encrypts api_keys with AES-256-GCM keyed by scrypt(STORAGE_ENCRYPTION_KEY,
"omniroute-field-encryption-v1", 32). We decrypt and INSERT into provider_keys.

Usage:
    python -m sonya.tools.import_omniroute_keys /path/to/omniroute_storage.sqlite \
        --enc-key 0110c474... \
        [--providers fireworks,openrouter] [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from pathlib import Path

from sonya.config import load_config
from sonya.providers.keystore import KeyStore
from sonya.state.substrate import Substrate


def _derive_key(storage_key_hex: str) -> bytes:
    return hashlib.scrypt(
        storage_key_hex.encode("utf-8"),
        salt=b"omniroute-field-encryption-v1",
        n=16384, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024,
    )


def _decrypt(blob: str, key: bytes) -> str | None:
    if not blob or not blob.startswith("enc:v1:"):
        return blob
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    parts = blob[len("enc:v1:"):].split(":")
    if len(parts) != 3:
        return None
    iv, ct, tag = (bytes.fromhex(p) for p in parts)
    try:
        return AESGCM(key).decrypt(iv, ct + tag, None).decode("utf-8")
    except Exception:
        return None


_PROVIDER_BASE_URL = {
    "fireworks": "https://api.fireworks.ai/inference/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepinfra": "https://api.deepinfra.com/v1/openai",
    "together": "https://api.together.xyz/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "openai": "https://api.openai.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import OmniRoute provider keys into Sonya KeyStore")
    parser.add_argument("storage_path", type=Path)
    parser.add_argument("--enc-key", required=True, help="OmniRoute STORAGE_ENCRYPTION_KEY (hex)")
    parser.add_argument("--providers", default="fireworks,openrouter,groq,deepinfra,together,cerebras")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.storage_path.exists():
        print(f"Not found: {args.storage_path}", file=sys.stderr)
        return 2

    providers = {p.strip().lower() for p in args.providers.split(",") if p.strip()}
    aes_key = _derive_key(args.enc_key)

    src = sqlite3.connect(str(args.storage_path))
    rows = src.execute(
        "SELECT id, provider, name, email, api_key, is_active, test_status "
        "FROM provider_connections WHERE auth_type='apikey'"
    ).fetchall()
    src.close()

    sub = Substrate.open(load_config().substrate_path)
    try:
        store = KeyStore(sub)
        existing = store.list_keys()
        existing_secrets = {k.api_key for k in existing}

        imported = 0
        skipped_dup = 0
        skipped_other_provider = 0
        skipped_decrypt = 0
        for pid, prov, name, email, enc_key, is_active, tstatus in rows:
            if (prov or "").lower() not in providers:
                skipped_other_provider += 1
                continue
            decrypted = _decrypt(enc_key, aes_key) if enc_key else None
            if not decrypted or decrypted.startswith("[DECRYPT_FAIL"):
                skipped_decrypt += 1
                continue
            if decrypted in existing_secrets:
                skipped_dup += 1
                continue
            label = (name or email or pid)[:80]
            base_url = _PROVIDER_BASE_URL.get(prov.lower(), "")
            if args.dry_run:
                print(f"[dry] would import: {prov} | {label} | {decrypted[:6]}...")
                imported += 1
                continue
            store.add_key(
                provider=prov.lower(),
                name=label,
                api_key=decrypted,
                base_url=base_url,
                model="",
                priority=0,
            )
            # If the source had test_status='unavailable', mark it disabled
            if (tstatus or "") == "unavailable":
                # Find what we just created (by api_key match)
                latest = next((k for k in store.list_keys(prov.lower()) if k.api_key == decrypted), None)
                if latest is not None:
                    from sonya.providers.keystore import KeyStatus as _KS
                    store.update_status(latest.key_id, _KS.DISABLED, last_error="imported as unavailable from omniroute")
            imported += 1

        prefix = "DRY RUN: " if args.dry_run else ""
        print(f"{prefix}imported={imported} dup={skipped_dup} "
              f"other_provider={skipped_other_provider} decrypt_fail={skipped_decrypt}")
        return 0
    finally:
        sub.close()


if __name__ == "__main__":
    sys.exit(main())
