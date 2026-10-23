import json
from pathlib import Path

import httpx

from genomic_evidence_agent.tools.pubmed import get_article_details, parse_pubmed_summary, search_pubmed

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_pubmed_summary_keeps_pmid_order():
    payload = {
        "result": {
            "uids": ["2", "1"],
            "1": {
                "title": "First paper",
                "source": "Nat Genet",
                "pubdate": "2020 Jan",
                "authors": [{"name": "Ada A"}, {"name": "Bea B"}],
                "articleids": [{"idtype": "doi", "value": "10.1/first"}],
            },
            "2": {
                "title": "Second paper",
                "source": "Science",
                "pubdate": "2021",
                "authors": [],
                "articleids": [],
            },
        }
    }
    articles = parse_pubmed_summary(payload, ["2", "1"])
    assert [article["pmid"] for article in articles] == ["2", "1"]
    assert articles[1]["doi"] == "10.1/first"
    assert articles[1]["authors"] == ["Ada A", "Bea B"]


def test_search_pubmed_uses_esearch_then_esummary():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/esearch.fcgi"):
            assert request.url.params["term"] == "BRCA1"
            assert request.url.params["api_key"] == "secret"
            return httpx.Response(200, json={"esearchresult": {"idlist": ["42"]}})
        body = {
            "result": {
                "42": {
                    "title": "BRCA1 study",
                    "source": "Nature",
                    "pubdate": "2024",
                    "authors": [{"name": "Lee L"}],
                    "articleids": [{"idtype": "pubmed", "value": "42"}],
                }
            }
        }
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        payload = search_pubmed("BRCA1", max_results=3, api_key="secret", client=client)
    expected = json.loads((FIXTURES / "pubmed_search_expected.json").read_text(encoding="utf-8"))
    assert payload["query"] == expected["query"]
    assert payload["n_results"] == expected["n_results"]
    article = payload["articles"][0]
    expected_article = expected["articles"][0]
    assert article["pmid"] == expected_article["pmid"]
    assert article["title"] == expected_article["title"]
    assert article["journal"] == expected_article["journal"]


ARTICLE_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>28061825</PMID>
      <Article>
        <Journal>
          <ISOAbbreviation>BMC Med Genet</ISOAbbreviation>
          <JournalIssue>
            <PubDate><Year>2017</Year><Month>Jan</Month><Day>7</Day></PubDate>
          </JournalIssue>
        </Journal>
        <ArticleTitle>New CDH3 mutation in the first Spanish case of hypotrichosis with juvenile macular dystrophy, a case report.</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">A CDH3 case.</AbstractText>
          <AbstractText Label="CONCLUSION">The variant was reported.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author><LastName>Blanco-Kelly</LastName><ForeName>F</ForeName></Author>
          <Author><LastName>Ayuso</LastName><ForeName>C</ForeName></Author>
        </AuthorList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">28061825</ArticleId>
        <ArticleId IdType="doi">10.1186/s12881-016-0364-5</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


def test_get_article_details_reads_metadata_and_abstract():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/efetch.fcgi")
        assert request.url.params["id"] == "28061825"
        assert request.url.params["db"] == "pubmed"
        assert request.url.params["retmode"] == "xml"
        assert request.url.params["api_key"] == "secret"
        return httpx.Response(200, text=ARTICLE_XML)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        payload = get_article_details("PMID: 28061825", api_key="secret", client=client)
    expected = json.loads((FIXTURES / "pubmed_article_expected.json").read_text(encoding="utf-8"))
    assert payload == expected


def test_get_article_details_rejects_a_missing_pmid():
    assert get_article_details("   ")["error"] == "Provide a PubMed PMID."


def test_get_article_details_reports_an_unknown_pmid():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<PubmedArticleSet></PubmedArticleSet>")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        payload = get_article_details("999", client=client)
    assert payload["pmid"] == "999"
    assert "No PubMed record" in payload["error"]
