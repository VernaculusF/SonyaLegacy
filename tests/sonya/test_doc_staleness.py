import re
from datetime import datetime
from pathlib import Path

def test_canonical_docs_staleness():
    docs_dir = Path(__file__).parent.parent.parent / "docs"
    canonical_files = ["STATE.md", "HANDOFF.md"]
    
    for filename in canonical_files:
        p = docs_dir / filename
        assert p.exists(), f"{filename} is missing"
        
        content = p.read_text(encoding="utf-8")
        
        # Find "**Last updated:** YYYY-MM-DD"
        match = re.search(r"\*\*Last updated:\*\*\s+(\d{4}-\d{2}-\d{2})", content)
        assert match is not None, f"{filename} missing '**Last updated:** YYYY-MM-DD' marker"
        
        date_str = match.group(1)
        updated_date = datetime.strptime(date_str, "%Y-%m-%d")
        days_old = (datetime.utcnow() - updated_date).days
        
        # Docs should be updated at least every 30 days
        assert days_old < 30, f"{filename} is stale by {days_old} days (last updated {date_str})"
