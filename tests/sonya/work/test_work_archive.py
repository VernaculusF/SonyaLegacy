import json
import hashlib
from sonya.state.substrate import Substrate
from sonya.work.store import WorkItemStore
from sonya.work.service import WorkItemService
from sonya.work.models import WorkItemStatus

def test_archive_manifest_and_checksum(tmp_path):
    sub = Substrate.open(tmp_path / "test.db")
    store = WorkItemStore(sub)
    service = WorkItemService(store)
    
    item = service.create(title="Test Archive Item", description="My description")
    
    # Add some progress and evidence
    service.append_progress(item.item_id, "Did step 1")
    service.complete(item.item_id, "All done")
    
    # Archive it
    archived_item = service.archive(item.item_id)
    
    assert archived_item.status == WorkItemStatus.ARCHIVED
    assert archived_item.archive_checksum != ""
    assert archived_item.archive_manifest != "{}"
    
    # Validate the contents of the manifest
    manifest_data = json.loads(archived_item.archive_manifest)
    assert manifest_data["title"] == "Test Archive Item"
    assert manifest_data["description"] == "My description"
    assert manifest_data["final_status"] == "done"
    assert manifest_data["progress_steps"] == 1
    assert manifest_data["evidence_count"] == 1
    
    # Validate the checksum matches the manifest exactly
    # Since separators=(',', ':') was used, recreate it here
    expected_manifest_str = json.dumps(manifest_data, separators=(',', ':'))
    expected_checksum = hashlib.sha256(expected_manifest_str.encode("utf-8")).hexdigest()
    
    assert archived_item.archive_checksum == expected_checksum
    
    # Test restore
    restored = service.restore(item.item_id)
    assert restored.status == WorkItemStatus.PENDING
