from app.industries import STANDARD_INDUSTRIES, standardize_industry as s


def test_official_labels_map_to_standard():
    assert s("教育・広告・その他サービス業") == "サービス業"
    assert s("公務員・公立学校教員") == "公務"
    assert s("漁業・農業・林業・鉱業") == "農林漁業・鉱業"
    assert s("学術研究，専門・技術サービス業") == "サービス業"
    assert s("卸売業・小売業") == "卸売業・小売業"


def test_demo_labels_map_to_standard():
    assert s("小売") == s("商社") == "卸売業・小売業"
    assert s("IT・通信") == "情報通信業"
    assert s("コンサル") == "サービス業"


def test_always_standard():
    for label in ["謎の区分", "", "その他", "医療，福祉", "電気・ガス・熱供給・水道業"]:
        assert s(label) in STANDARD_INDUSTRIES


def test_school_destinations_are_education():
    for label in ["小学校", "中学校・高等学校", "幼稚園", "保育所", "こども園"]:
        assert s(label) == "サービス業"
    assert s("公立学校教員") == "公務"
    assert s("マスコミ") == "情報通信業"
