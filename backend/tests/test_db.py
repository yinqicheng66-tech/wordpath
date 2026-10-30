import ssl

from app.db import engine_args


def test_local_url_is_unchanged():
    url = "postgresql+pg8000://wordpath:wordpath@localhost:5432/wordpath"
    assert engine_args(url) == (url, {})


def test_hosted_url_gets_driver_and_ssl():
    url, args = engine_args(
        "postgresql://user:pw@ep-cool-1.us-east-2.aws.neon.tech/wordpath"
        "?sslmode=require&channel_binding=require"
    )
    assert url == "postgresql+pg8000://user:pw@ep-cool-1.us-east-2.aws.neon.tech/wordpath"
    assert isinstance(args["ssl_context"], ssl.SSLContext)


def test_heroku_style_scheme():
    url, args = engine_args("postgres://u:p@host:5432/db")
    assert url == "postgresql+pg8000://u:p@host:5432/db"
    assert args == {}


def test_sqlite_is_left_alone():
    assert engine_args("sqlite:///./test.db") == ("sqlite:///./test.db", {})


def test_in_memory_sqlite_is_left_alone():
    assert engine_args("sqlite://") == ("sqlite://", {})
