"""Exercise probe ownership and error redaction without contacting a server."""
import mongomock
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError

from scripts.check_integration_services import PROBE_DATABASE, mongo_crud, mongo_error


def test_crud_probe_leaves_other_documents_intact():
    with mongomock.MongoClient() as client:
        collection = client[PROBE_DATABASE].phase21_probes
        existing = {'_id': 'unrelated', 'owner': 'another-process', 'value': 9}
        collection.insert_one(existing)
        mongo_crud(client)
        assert list(collection.find()) == [existing]


def test_probe_errors_do_not_echo_connection_details():
    detail = 'example connection detail'
    assert mongo_error(DuplicateKeyError(detail)) == 'FAIL: duplicate key'
    assert detail not in mongo_error(ServerSelectionTimeoutError(detail))
