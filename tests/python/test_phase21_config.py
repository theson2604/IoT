from gateway.app.config import Settings


def test_secret_configuration_is_not_in_repr():
    settings=Settings(mongodb_uri='mongodb://example-user:example-secret@localhost/',mqtt_password='example-mqtt-secret')
    assert 'example-secret' not in repr(settings)
    assert 'example-mqtt-secret' not in repr(settings)


def test_real_fixture_configuration_uses_dotenv(tmp_path,monkeypatch):
    # Test dotenv precedence with a synthetic URI, never a real credential.
    from gateway.app import config
    path=tmp_path/'config.py'
    path.write_text('')
    # config.__file__.parents[1] is used to locate gateway/.env.
    module_path=tmp_path/'app'/'config.py'
    module_path.parent.mkdir()
    monkeypatch.setattr(config,'__file__',str(module_path))
    monkeypatch.delenv('MONGODB_URI',raising=False)
    monkeypatch.delenv('MONGODB_DATABASE',raising=False)
    # Ensure dotenv's environment changes are reverted by monkeypatch.
    monkeypatch.setenv('MONGODB_URI','')
    monkeypatch.delenv('MONGODB_URI')
    (tmp_path/'.env').write_text('MONGODB_URI=mongodb://127.0.0.1:27018/\n')
    assert Settings.from_env().mongodb_uri=='mongodb://127.0.0.1:27018/'
