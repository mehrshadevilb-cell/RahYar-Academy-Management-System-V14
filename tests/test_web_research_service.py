from src.services.web_research_service import WebResearchService


class FakeResearch(WebResearchService):
    def __init__(self):
        self.pages = {
            "https://example.com/manual": "<html><body><h1>Manual</h1><p>Set buffer size in Preferences.</p></body></html>",
        }

    def _get(self, url: str, timeout: int = 12) -> str:
        if "duckduckgo" in url:
            return """<a class='result__a' href='https://example.com/manual'>Example Manual</a>"""
        return self.pages[url]


def test_research_extracts_result_and_page_text():
    result = FakeResearch().research("DAW buffer size", limit=1)
    assert "Example Manual" in result
    assert "https://example.com/manual" in result
    assert "Set buffer size in Preferences." in result


def test_research_handles_search_failure():
    class Broken(FakeResearch):
        def _get(self, url: str, timeout: int = 12) -> str:
            raise OSError("offline")

    assert Broken().research("unknown") == ""
