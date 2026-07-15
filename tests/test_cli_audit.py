import json

from fashion_personalization import cli


def test_cli_audit_output_has_required_portfolio_fields(capsys) -> None:
    exit_code = cli.main()
    captured = capsys.readouterr()

    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["verificationScope"] == "local-deterministic"
    assert payload["adminReport"]["products"] == 6
    assert payload["adminReport"]["event_watermark"] is not None
    assert payload["sampleRecommendations"]
    assert payload["latestSnapshot"]["recommendations"]
    assert payload["claimBoundary"]
