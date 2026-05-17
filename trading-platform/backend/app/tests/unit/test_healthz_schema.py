from app.main import ServiceHealthModel


def test_service_health_model() -> None:
    model = ServiceHealthModel(status="ok")
    assert model.status == "ok"
    assert model.detail is None

