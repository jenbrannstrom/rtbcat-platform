from types import SimpleNamespace

from api.main import resolve_serving_dsn


def test_deployment_serving_dsn_overrides_restored_provider_config(monkeypatch) -> None:
    restored_config = SimpleNamespace(
        database=SimpleNamespace(
            serving_postgres_dsn="postgresql://legacy-cloud-provider/database"
        )
    )
    monkeypatch.setenv(
        "POSTGRES_SERVING_DSN",
        "postgresql://private-hetzner-target/database",
    )

    assert resolve_serving_dsn(restored_config) == (
        "postgresql://private-hetzner-target/database"
    )


def test_restored_serving_dsn_remains_fallback_without_deployment_env(monkeypatch) -> None:
    restored_config = SimpleNamespace(
        database=SimpleNamespace(
            serving_postgres_dsn="postgresql://legacy-cloud-provider/database"
        )
    )
    monkeypatch.delenv("POSTGRES_SERVING_DSN", raising=False)

    assert resolve_serving_dsn(restored_config) == (
        "postgresql://legacy-cloud-provider/database"
    )
