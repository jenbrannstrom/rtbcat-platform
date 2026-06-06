import pytest

from collectors.creatives.client import CreativesClient
from collectors.creatives.parsers import parse_creative_response
from storage.adapters import creative_dict_to_storage


class _Request:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


@pytest.mark.asyncio
async def test_get_creative_by_id_encodes_buyer_resource_name(monkeypatch) -> None:
    buyer_get_names = []
    creative_id = "abc+def/ghi"

    class _BiddersCreatives:
        def list(self, **params):
            assert params["filter"] == f'creativeId="{creative_id}"'
            return _Request({
                "creatives": [
                    {
                        "name": f"bidders/123/creatives/{creative_id}",
                        "html": {"snippet": "<html></html>", "width": 300, "height": 250},
                    }
                ]
            })

    class _BuyersCreatives:
        def get(self, **params):
            buyer_get_names.append(params["name"])
            return _Request({"name": params["name"]})

    class _Bidders:
        def creatives(self):
            return _BiddersCreatives()

    class _Buyers:
        def creatives(self):
            return _BuyersCreatives()

    class _Service:
        def bidders(self):
            return _Bidders()

        def buyers(self):
            return _Buyers()

    client = CreativesClient(credentials_path=None, account_id="123")
    monkeypatch.setattr(client, "_get_service", lambda: _Service())

    async def execute(request_func):
        return request_func().execute()

    monkeypatch.setattr(client, "_execute_with_retry", execute)

    result = await client.get_creative_by_id(creative_id, buyer_id="6574658621")

    assert result is not None
    assert result["creativeId"] == creative_id
    assert buyer_get_names == ["buyers/6574658621/creatives/abc%2Bdef%2Fghi"]


def test_parse_creative_response_preserves_google_language_metadata() -> None:
    parsed = parse_creative_response(
        {
            "name": "bidders/123/creatives/creative-1",
            "creativeId": "creative-1",
            "creativeFormat": "HTML",
            "previewUrl": "https://storage.googleapis.com/preview/ad",
            "renderUrl": "https://render.example.com/ad",
            "creativeServingDecision": {"detectedLanguages": ["hi"]},
            "html": {"width": 320, "height": 50},
        },
        "123",
        buyer_id="1487810529",
    )

    creative = creative_dict_to_storage(parsed)

    assert parsed["format"] == "HTML"
    assert parsed["previewUrl"] == "https://storage.googleapis.com/preview/ad"
    assert parsed["renderUrl"] == "https://render.example.com/ad"
    assert parsed["creativeServingDecision"] == {"detectedLanguages": ["hi"]}
    assert creative.raw_data["previewUrl"] == "https://storage.googleapis.com/preview/ad"
    assert creative.raw_data["renderUrl"] == "https://render.example.com/ad"
    assert creative.raw_data["creativeServingDecision"] == {"detectedLanguages": ["hi"]}
