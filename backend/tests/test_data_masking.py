from __future__ import annotations

from core.data_masking import MaskingResult, mask_sensitive_data


def test_mask_amount() -> None:
    result = mask_sensitive_data("合同金额100.00万元")
    assert "[金额]" in result.text
    assert "100.00" not in result.text


def test_mask_amount_yuan() -> None:
    result = mask_sensitive_data("总计金额500,50元")
    assert "[金额]" in result.text


def test_mask_amount_billion() -> None:
    result = mask_sensitive_data("投资额3.5亿元")
    assert "[金额]" in result.text


def test_mask_phone() -> None:
    result = mask_sensitive_data("联系电话13812345678")
    assert "[手机号***]" in result.text
    assert "13812345678" not in result.text


def test_mask_id_card() -> None:
    result = mask_sensitive_data("身份证号110101199001011234")
    assert "[身份证***]" in result.text
    assert "110101199001011234" not in result.text


def test_mask_bank_card() -> None:
    result = mask_sensitive_data("银行卡6222021234567890123")
    assert "[银行卡***]" in result.text
    assert "6222021234567890123" not in result.text


def test_mask_email() -> None:
    result = mask_sensitive_data("邮箱test@example.com")
    assert "[邮箱***]" in result.text
    assert "test@example.com" not in result.text


def test_mixed_text() -> None:
    text = "联系人张三，手机13912345678，身份证110101199001011234，金额100.00万元，邮箱zhang@test.com"
    result = mask_sensitive_data(text)
    assert "[手机号***]" in result.text
    assert "[身份证***]" in result.text
    assert "[金额]" in result.text
    assert "[邮箱***]" in result.text
    assert "13912345678" not in result.text
    assert "110101199001011234" not in result.text
    assert "100.00万元" not in result.text
    assert "zhang@test.com" not in result.text


def test_no_sensitive_info_unchanged() -> None:
    text = "这是一段普通文本，没有敏感信息。"
    result = mask_sensitive_data(text)
    assert result.text == text
    assert result.masked_count == 0


def test_date_not_masked() -> None:
    result = mask_sensitive_data("签订日期2026年6月11日")
    assert "2026年6月11日" in result.text
    assert "[银行卡***]" not in result.text


def test_date_with_full_numbers_not_masked() -> None:
    result = mask_sensitive_data("项目从2024年1月15日开始至2025年12月31日结束")
    assert "2024年1月15日" in result.text
    assert "2025年12月31日" in result.text


def test_empty_string() -> None:
    result = mask_sensitive_data("")
    assert result.text == ""
    assert result.masked_count == 0


def test_masking_result_count() -> None:
    text = "手机13812345678，手机13987654321，邮箱a@b.com"
    result = mask_sensitive_data(text)
    assert result.masked_count == 3


def test_masking_result_type() -> None:
    result = mask_sensitive_data("金额100.00万元")
    assert isinstance(result, MaskingResult)
    assert isinstance(result.text, str)
    assert isinstance(result.mask_map, dict)
    assert isinstance(result.masked_count, int)


def test_id_card_not_double_matched_as_bank_card() -> None:
    result = mask_sensitive_data("身份证110101199001011234")
    assert "[身份证***]" in result.text
    assert "[银行卡***]" not in result.text


def test_bank_card_16_digits() -> None:
    result = mask_sensitive_data("卡号6222021234567890")
    assert "[银行卡***]" in result.text


def test_phone_not_embedded_in_longer_number() -> None:
    result = mask_sensitive_data("编号1381234567890")
    assert "[手机号***]" not in result.text


from app.prompts.inspection_prompts import format_inspection_prompt, format_regulation_prompt


def test_format_regulation_prompt_masks_phone() -> None:
    prompt = format_regulation_prompt("联系电话13812345678", max_length=6000)
    assert "[手机号***]" in prompt
    assert "13812345678" not in prompt


def test_format_inspection_prompt_masks_id_card() -> None:
    prompt = format_inspection_prompt(
        "身份证号110101199001011234",
        "法规分析结果",
        max_length=6000,
    )
    assert "[身份证***]" in prompt
    assert "110101199001011234" not in prompt


def test_format_prompt_keeps_normal_text() -> None:
    prompt = format_regulation_prompt("普通文档内容", max_length=6000)
    assert "普通文档内容" in prompt
