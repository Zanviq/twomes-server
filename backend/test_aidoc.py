"""AI 문서 시스템(aidoc) 테스트. assert 함수 + __main__ 러너."""
import os, tempfile, json

os.environ["STORAGE_ROOT"] = tempfile.mkdtemp(prefix="aidoc_test_")
os.environ["AUTH_USERS"] = json.dumps([{"username": "tester", "password": "pw", "display_name": "T"}])
os.environ["SESSION_SECRET"] = "aidoc-test-secret"
os.environ["DOCUMENT_ROOT"] = os.path.join(os.environ["STORAGE_ROOT"], "AI_documents")
os.environ["AIDOC_DB_PATH"] = os.path.join(os.environ["STORAGE_ROOT"], "aidoc", "documents.db")
os.environ["AIDOC_TOKENS_FILE"] = os.path.join(os.environ["STORAGE_ROOT"], "aidoc", "tokens.json")
os.environ["AIDOC_PROJECTS"] = "orchestra-room,nodi"

from backend.config import Settings  # noqa: E402


def test_settings_aidoc():
    s = Settings()
    assert s.document_root.name == "AI_documents"
    assert str(s.aidoc_db_path).endswith("documents.db")
    assert s.aidoc_projects == ["orchestra-room", "nodi"]
    assert s.aidoc_max_bytes == 1048576


if __name__ == "__main__":
    test_settings_aidoc()
    print("OK")
