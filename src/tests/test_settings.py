import pytest

from settings import SafeSettings


class ExampleSettings(SafeSettings):
    required = {"SERVICE_HOST", "SERVICE_TOKEN"}

    def __init__(self, host, token):
        self.host = host
        self.token = token

    @classmethod
    def from_values(cls, values):
        return cls(host=values["SERVICE_HOST"], token=values["SERVICE_TOKEN"])


def test_validate_allows_no_requirements():
    SafeSettings.validate({})


def test_validate_accepts_required_values():
    ExampleSettings.validate({"SERVICE_HOST": "localhost", "SERVICE_TOKEN": "token"})
    assert True  # INFO: no exception raised


@pytest.mark.parametrize(
    "values",
    [
        {"SERVICE_HOST": "localhost"},
        {"SERVICE_HOST": "localhost", "SERVICE_TOKEN": ""},
    ],
)
def test_validate_rejects_missing_or_empty_values(values):
    with pytest.raises(
        ValueError, match=r"^ExampleSettings is misconfigured\. Missing: SERVICE_TOKEN$"
    ):
        ExampleSettings.validate(values)


def test_validate_reports_missing_keys_in_sorted_order():
    with pytest.raises(
        ValueError,
        match=r"^ExampleSettings is misconfigured\. Missing: SERVICE_HOST, SERVICE_TOKEN$",
    ):
        ExampleSettings.validate({})


def test_from_environment_passes_environment_to_from_values(monkeypatch):
    values = {"SERVICE_HOST": "localhost", "SERVICE_TOKEN": "token", "EXTRA": "value"}
    monkeypatch.setattr("settings.environ", values)

    settings = ExampleSettings.from_environment()

    assert isinstance(settings, ExampleSettings)
    assert settings.host == "localhost"
    assert settings.token == "token"


@pytest.mark.parametrize(
    "values",
    [
        {"SERVICE_HOST": "localhost"},
        {"SERVICE_HOST": "localhost", "SERVICE_TOKEN": ""},
    ],
)
def test_from_environment_validates_before_calling_from_values(monkeypatch, values):
    monkeypatch.setattr("settings.environ", values)

    def unexpected_from_values(cls, values):
        pytest.fail("from_values must not be called with an invalid environment")

    monkeypatch.setattr(ExampleSettings, "from_values", classmethod(unexpected_from_values))

    with pytest.raises(
        ValueError, match=r"^ExampleSettings is misconfigured\. Missing: SERVICE_TOKEN$"
    ):
        ExampleSettings.from_environment()
