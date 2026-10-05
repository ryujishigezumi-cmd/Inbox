from app.normalize import normalize_company_name as n


def test_variants_collapse():
    keys = {n(x) for x in ["株式会社ニトリ", "ニトリ", "ニトリグループ", "(株)ニトリ", "ニトリホールディングス", "ﾆﾄﾘ"]}
    assert keys == {"ニトリ"}


def test_fullwidth():
    assert n("三菱ＵＦＪ銀行") == n("株式会社三菱UFJ銀行")


def test_does_not_strip_whole_name():
    assert n("グループ") == "グループ"
