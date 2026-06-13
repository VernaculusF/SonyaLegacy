import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sonya.state import Substrate
from sonya.providers.keystore import KeyStore
from sonya.providers.llm_provider import LLMProvider

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Gauntlet Scenarios
SCENARIOS = [
    {
        "name": "complex_tool_extraction",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful AI. You must use tools by returning a JSON block starting with [TOOL: tool_name] ... [/TOOL]. Available tools: search(query: str)"
            },
            {
                "role": "user",
                "content": "Please perform a search for 'Model Evaluation Best Practices' and return the result."
            }
        ],
        "validation": lambda text: "[TOOL: search]" in text and "Model Evaluation Best Practices" in text
    },
    {
        "name": "syntax_error_fixing",
        "messages": [
            {
                "role": "user",
                "content": "Fix the syntax error in this Python code and return ONLY the corrected code without markdown backticks:\n\ndef add(a, b)\n    return a + b"
            }
        ],
        "validation": lambda text: "def add(a, b):" in text and "return a + b" in text
    },
    {
        "name": "implicit_instructions",
        "messages": [
            {
                "role": "system",
                "content": "You have a tool chat.tell_ivan(message: str) to message the user. Return it in [TOOL: chat.tell_ivan] JSON_ARGS [/TOOL]."
            },
            {
                "role": "user",
                "content": "tell Ivan I found the keys"
            }
        ],
        "validation": lambda text: "[TOOL: chat.tell_ivan]" in text and ("found the keys" in text.lower() or "нашла ключи" in text.lower() or "keys" in text.lower())
    }
]

async def eval_model(llm: LLMProvider, provider: str, model: str) -> dict:
    results = {}
    for sc in SCENARIOS:
        try:
            resp = await llm.complete_text(
                messages=sc["messages"],
                purpose="active_session",
                provider=provider,
                model=model,
                temperature=0.0
            )
            passed = sc["validation"](resp)
            results[sc["name"]] = {"passed": passed, "output": resp}
        except Exception as e:
            results[sc["name"]] = {"passed": False, "error": str(e)}
    return results

async def main():
    parser = argparse.ArgumentParser(description="Model Acceptance Testing System")
    parser.add_argument("--db-path", type=str, default="workspace/s.db", help="Path to Sonya SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Do not disable models in DB, just print results")
    parser.add_argument("--encryption-key", type=str, default="", help="Secret encryption key for KeyStore")
    args = parser.parse_args()

    db_file = Path(args.db_path)
    if False:
        logging.error(f"Database not found at {db_file}")
        return

    sub = Substrate.open(db_file)
    store = KeyStore(sub, secret_encryption_key=args.encryption_key.encode() if args.encryption_key else None)
    llm = LLMProvider(store)

    # Fetch active models
    rows = sub.connection.execute('''
        SELECT o.model_id, a.provider_id, o.account_id 
        FROM provider_account_offerings o
        JOIN provider_accounts a ON o.account_id = a.account_id
        WHERE o.enabled = 1
    ''').fetchall()
    
    if not rows:
        logging.info("No enabled models found in provider_account_offerings.")
        sub.close()
        return

    logging.info(f"Found {len(rows)} enabled models to test.")
    
    for row in rows:
        model_id = row[0]
        provider_id = row[1]
        account_id = row[2]
        
        logging.info(f"--- Evaluating model: {model_id} (Provider: {provider_id}) ---")
        
        results = await eval_model(llm, provider_id, model_id)
        
        total = len(SCENARIOS)
        passed = sum(1 for r in results.values() if r.get("passed"))
        
        logging.info(f"Result for {model_id}: {passed}/{total} passed")
        
        for sc_name, sc_res in results.items():
            status = "PASS" if sc_res.get("passed") else "FAIL"
            logging.info(f"  [{status}] {sc_name}")
            if not sc_res.get("passed"):
                logging.debug(f"    Output/Error: {sc_res.get('output') or sc_res.get('error')}")
                
        # Policy: disable if it fails any tests
        if passed < total:
            if args.dry_run:
                logging.warning(f"[DRY-RUN] Would disable model {model_id} on account {account_id}")
            else:
                logging.warning(f"Disabling model {model_id} on account {account_id}")
                sub.connection.execute(
                    "UPDATE provider_account_offerings SET enabled = 0 WHERE account_id = ? AND model_id = ?",
                    (account_id, model_id)
                )
                sub.connection.commit()

    sub.close()

if __name__ == "__main__":
    asyncio.run(main())
