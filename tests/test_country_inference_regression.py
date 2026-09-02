from data_pipeline.xls_parser import XLSPipeline


def test_country_inference_covers_known_country_sheet_names():
    expected = {
        "巴西专线小包DDU": "巴西",
        "巴西专线小包（免税）": "巴西",
        "智利专线小包": "智利",
        "秘鲁专线小包": "秘鲁",
        "阿根廷专线小包": "阿根廷",
        "以色列专线小包": "以色列",
        "英国快速小包-纯普货": "英国",
        "英国头程虚拟专线小包": "英国",
        "美国专线小包": "美国",
        "加拿大专线小包": "加拿大",
        "墨西哥专线小包": "墨西哥",
        "哥伦比亚专线小包": "哥伦比亚",
        "澳洲专线小包": "澳洲",
        "澳洲特货小包": "澳洲",
        "E速宝(俄罗斯)-A": "俄罗斯",
        "日本专线小包": "日本",
    }
    for sheet_name, country in expected.items():
        assert XLSPipeline._infer_country(sheet_name, None) == country


def test_country_inference_supports_spain_portugal_sheet():
    assert XLSPipeline._infer_country("西葡专线小包", None) == "西班牙、葡萄牙"


def test_country_inference_does_not_turn_regions_into_single_countries():
    assert XLSPipeline._infer_country("欧美标准专线", None) is None
    assert XLSPipeline._infer_country("欧洲快线小包", None) is None
    assert XLSPipeline._infer_country("泛欧特惠小包", None) is None
    assert XLSPipeline._infer_country("中东专线小包", None) is None
