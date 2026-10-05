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


def test_welfare_is_not_finance():
    assert s("社会保険・社会福祉・介護事業") == "サービス業"
    assert s("保険業") == "金融業・保険業"


def test_ambiguous_labels():
    assert s("食品卸売業") == "卸売業・小売業"
    assert s("私立学校教員・職員") == "サービス業"
    assert s("国公立学校教員・職員") == "公務"
    assert s("旅行・生活関連サービス") == "サービス業"
    assert s("信用金庫・信用組合・労働金庫業 等") == "金融業・保険業"
    assert s("印刷・同関連業") == "製造業"
    assert s("製造業：電気・情報通信機械器具製造業") == "製造業"
    assert s("情報") == "情報通信業"


def test_teachers_public_only_when_public():
    assert s("教員（公立）") == s("公務員・公立学校教員") == s("国公立学校教員・職員") == "公務"
    assert s("教員（私立）") == s("教員（大学等）") == s("教員（その他）") == "サービス業"
