from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ChannelRate:
    sheet_name: str
    channel_name: str | None = None
    countries: str | None = None
    cargo_type: str | None = None
    weight_min: float | None = None
    weight_max: float | None = None
    price_per_kg: float | None = None
    handling_fee: float | None = None
    first_weight: float | None = None
    first_weight_price: float | None = None
    additional_weight: float | None = None
    additional_weight_price: float | None = None
    size_requirements: str | None = None
    transit_time: str | None = None
    carrier: str | None = None


@dataclass(frozen=True)
class ChannelRule:
    sheet_name: str
    channel_name: str | None = None
    rule_category: str = "其他"
    content: str = ""


class XLSPipeline:
    HEADER_KEYWORDS = ("渠道", "国家", "重量", "运费", "首", "续", "类型", "区域")
    RULE_KEYWORDS = ("申报", "赔偿", "赔付", "安检", "退件", "退回", "禁运", "尺寸", "时效", "体积", "超长", "超重", "查验", "理赔", "禁止运输", "不接")
    RULE_CATEGORIES = {
        "赔偿": ("赔偿", "赔付", "理赔", "丢失赔"),
        "禁运": ("禁运", "航空禁运", "禁止运输", "禁止寄运", "不接"),
        "尺寸": ("尺寸", "长宽高", "体积", "超长", "超重"),
        "退件": ("退件", "退回", "退费"),
        "申报": ("申报", "申报价值", "低报", "报关"),
        "安检": ("安检", "查验", "安全检查"),
        "时效": ("时效", "派送时效", "延误", "工作日"),
    }
    STANDALONE_RULE_SHEETS = ("易德赔付标准", "退费额外费要求", "航空禁运物品")
    PURE_HEADER_TERMS = ("规则类别", "规则内容", "内容", "说明", "备注", "物品名称", "类别", "序号", "国家", "渠道", "重量", "运费", "处理费", "尺寸要求", "参考时效")
    COUNTRY_COMPOSITE_SHEETS = (
        ("西葡", "西班牙、葡萄牙"),
    )

    def __init__(self, xls_path: str | Path):
        self.xls_path = Path(xls_path)
        if not self.xls_path.is_file():
            raise FileNotFoundError(self.xls_path)
        self._excel = pd.ExcelFile(self.xls_path, engine="xlrd")
        self.sheet_names = self._excel.sheet_names
        self.country_catalog = self._build_country_catalog()

    def parse_all(self) -> list[ChannelRate]:
        rows: list[ChannelRate] = []
        for sheet_name in self.sheet_names:
            rows.extend(self.parse_sheet(sheet_name))
        return rows

    def parse_sheet(self, sheet_name: str) -> list[ChannelRate]:
        raw = pd.read_excel(self._excel, sheet_name=sheet_name, header=None)
        header_row = self._find_header_row(raw)
        if header_row is None:
            return []
        if self._is_zone_table(raw, header_row):
            return self._parse_zone_table(raw, header_row, sheet_name)
        headers = self._build_headers(raw, header_row)
        data = raw.iloc[header_row + self._header_height(raw, header_row):].copy()
        data.columns = headers
        data = data.dropna(how="all")
        channel_col = self._find_col(data.columns, "渠道")
        country_col = self._find_col(data.columns, "国家")
        cargo_col = self._find_col(data.columns, "接货类型", "货物类型")
        weight_col = self._find_col(data.columns, "重量", "重量段")
        price_col = self._find_col(data.columns, "运费/KG", "运费", "价格/KG")
        handling_col = self._find_col(data.columns, "处理费")
        first_col = self._find_col(data.columns, "首0.5KG", "首重")
        additional_col = self._find_col(data.columns, "续0.5KG", "续重")
        size_col = self._find_col(data.columns, "尺寸要求及附加费", "尺寸要求")
        transit_col = self._find_col(data.columns, "参考时效", "时效")
        carrier_col = self._find_col(data.columns, "承运商", "目的地承运商")
        fill_cols = [c for c in (channel_col, country_col, cargo_col, size_col, transit_col, carrier_col) if c]
        for col in fill_cols:
            data[col] = data[col].ffill()
        header_text = " ".join(str(c) for c in data.columns)
        results: list[ChannelRate] = []
        for _, row in data.iterrows():
            weight = self._parse_weight_range(row.get(weight_col)) if weight_col else None
            if not weight:
                continue
            channel = self._text(row.get(channel_col)) if channel_col else sheet_name
            country = self._text(row.get(country_col)) if country_col else self._infer_country(sheet_name, channel)
            accepted = self._text(row.get(cargo_col)) if cargo_col else None
            selected_price_header = str(price_col or "")
            cargo = self._infer_cargo_type(channel, accepted, f"{header_text} {selected_price_header}")
            price = self._number(row.get(price_col)) if price_col else None
            handling = self._number(row.get(handling_col)) if handling_col else None
            first_weight = self._weight_from_header(first_col)
            additional_weight = self._weight_from_header(additional_col)
            first_price = self._number(row.get(first_col)) if first_col else None
            additional_price = self._number(row.get(additional_col)) if additional_col else None
            results.append(ChannelRate(sheet_name=sheet_name, channel_name=channel, countries=country, cargo_type=cargo, weight_min=weight[0], weight_max=weight[1], price_per_kg=price, handling_fee=handling, first_weight=first_weight, first_weight_price=first_price, additional_weight=additional_weight, additional_weight_price=additional_price, size_requirements=self._text(row.get(size_col)) if size_col else None, transit_time=self._text(row.get(transit_col)) if transit_col else None, carrier=self._text(row.get(carrier_col)) if carrier_col else None))
        return results

    def extract_all_rules(self) -> list[ChannelRule]:
        rules: list[ChannelRule] = []
        for sheet_name in self.sheet_names:
            if any(name in sheet_name for name in self.STANDALONE_RULE_SHEETS):
                rules.extend(self.extract_rules_from_standalone_sheet(sheet_name))
            else:
                rules.extend(self.extract_rules_from_rate_sheet(sheet_name))
        return rules

    def extract_rules_from_rate_sheet(self, sheet_name: str) -> list[ChannelRule]:
        raw = pd.read_excel(self._excel, sheet_name=sheet_name, header=None)
        header_row = self._find_header_row(raw)
        if header_row is None:
            return []
        data_start = header_row + self._header_height(raw, header_row)
        weight_col = self._find_weight_column_index(raw, header_row)
        last_rate_row = self._find_last_rate_row(raw, data_start, weight_col)
        if last_rate_row is None:
            return []
        first_rule_row = self._find_first_rule_row(raw, last_rate_row + 1)
        if first_rule_row is None:
            return []
        channel_name = self._infer_rate_rule_channel(raw, sheet_name, data_start, last_rate_row)
        return self._extract_rule_rows(raw, sheet_name, channel_name, first_rule_row)

    def extract_rules_from_standalone_sheet(self, sheet_name: str) -> list[ChannelRule]:
        raw = pd.read_excel(self._excel, sheet_name=sheet_name, header=None)
        if raw.empty:
            return []
        rules: list[ChannelRule] = []
        for idx in range(len(raw)):
            content = self._row_text(raw.iloc[idx].tolist())
            if not content or self._is_meaningless_rule_content(content, sheet_name):
                continue
            rules.append(ChannelRule(sheet_name=sheet_name, channel_name=self._infer_standalone_rule_channel(content), rule_category=self._classify_rule_category(content), content=content))
        return rules

    @classmethod
    def _find_weight_column_index(cls, raw: pd.DataFrame, header_row: int) -> int | None:
        height = cls._header_height(raw, header_row)
        for col in range(raw.shape[1]):
            text = " ".join(cls._text(raw.iat[row, col]) or "" for row in range(header_row, header_row + height))
            if "重量" in text:
                return col
        return None

    @classmethod
    def _find_last_rate_row(cls, raw: pd.DataFrame, start_row: int, weight_col: int | None) -> int | None:
        if weight_col is None:
            return None
        last: int | None = None
        for idx in range(start_row, len(raw)):
            weight = cls._parse_weight_range(raw.iat[idx, weight_col])
            if not weight:
                continue
            numeric_values = sum(cls._number(value) is not None for value in raw.iloc[idx].tolist())
            if numeric_values >= 2:
                last = idx
        return last

    @classmethod
    def _find_first_rule_row(cls, raw: pd.DataFrame, start_row: int) -> int | None:
        for idx in range(start_row, len(raw)):
            content = cls._row_text(raw.iloc[idx].tolist())
            if content and cls._contains_rule_keyword(content):
                return idx
        return None

    @classmethod
    def _extract_rule_rows(cls, raw: pd.DataFrame, sheet_name: str, channel_name: str | None, start_row: int) -> list[ChannelRule]:
        rules: list[ChannelRule] = []
        blank_rows = 0
        for idx in range(start_row, len(raw)):
            content = cls._row_text(raw.iloc[idx].tolist())
            if not content:
                blank_rows += 1
                if rules and blank_rows >= 2:
                    break
                continue
            blank_rows = 0
            if cls._is_meaningless_rule_content(content, sheet_name):
                continue
            rules.append(ChannelRule(sheet_name=sheet_name, channel_name=cls._infer_rule_channel_from_content(content, channel_name), rule_category=cls._classify_rule_category(content), content=content))
        return rules

    @classmethod
    def _infer_rate_rule_channel(cls, raw: pd.DataFrame, sheet_name: str, start_row: int, end_row: int) -> str | None:
        header_row = cls._find_header_row(raw)
        if header_row is not None:
            channel_col = cls._find_column_index(raw, header_row, "渠道")
            if channel_col is not None:
                channels: list[str] = []
                for idx in range(start_row, end_row + 1):
                    channel = cls._text(raw.iat[idx, channel_col])
                    if channel and channel not in channels:
                        channels.append(channel)
                if len(channels) == 1:
                    return channels[0]
        return sheet_name or None

    @classmethod
    def _infer_standalone_rule_channel(cls, content: str) -> str | None:
        return cls._infer_rule_channel_from_content(content, None)

    @classmethod
    def _infer_rule_channel_from_content(cls, content: str, default: str | None) -> str | None:
        known_channels = ("美国专线小包", "日本专线小包", "欧美标准专线", "巴西专线小包DDU", "香港DHL代理价")
        for channel in known_channels:
            if channel in content:
                return channel
        return default

    @classmethod
    def _find_column_index(cls, raw: pd.DataFrame, header_row: int, *needles: str) -> int | None:
        height = cls._header_height(raw, header_row)
        for col in range(raw.shape[1]):
            text = " ".join(cls._text(raw.iat[row, col]) or "" for row in range(header_row, header_row + height))
            if any(needle in text for needle in needles):
                return col
        return None

    @classmethod
    def _row_text(cls, values: list[Any]) -> str | None:
        parts: list[str] = []
        for value in values:
            text = cls._text(value)
            if text and text not in parts:
                parts.append(text)
        return " ".join(parts) or None

    @classmethod
    def _contains_rule_keyword(cls, content: str) -> bool:
        return any(keyword in content for keyword in cls.RULE_KEYWORDS)

    @classmethod
    def _classify_rule_category(cls, content: str) -> str:
        for category, keywords in cls.RULE_CATEGORIES.items():
            if any(keyword in content for keyword in keywords):
                return category
        return "其他"

    @classmethod
    def _is_meaningless_rule_content(cls, content: str, sheet_name: str) -> bool:
        normalized = re.sub(r"[\s:：、,，/]+", "", content)
        if not normalized or normalized == re.sub(r"[\s:：、,，/]+", "", sheet_name):
            return True
        header_terms = {re.sub(r"[\s:：、,，/]+", "", term) for term in cls.PURE_HEADER_TERMS}
        tokens = [re.sub(r"[\s:：、,，/]+", "", token) for token in re.split(r"[\s]+", content) if token]
        if normalized in header_terms:
            return True
        return len(tokens) > 1 and all(token in header_terms for token in tokens)

    @classmethod
    def _header_height(cls, raw: pd.DataFrame, header_row: int) -> int:
        current_text = " ".join(cls._text(v) or "" for v in raw.iloc[header_row].tolist())
        next_text = " ".join(cls._text(v) or "" for v in raw.iloc[header_row + 1].tolist()) if header_row + 1 < len(raw) else ""
        if "国家" in current_text and ("运费/KG" in next_text or "处理费" in next_text):
            return 2
        return 1

    @classmethod
    def _build_headers(cls, raw: pd.DataFrame, header_row: int) -> list[str]:
        height = cls._header_height(raw, header_row)
        headers: list[str] = []
        for col in range(raw.shape[1]):
            parts = []
            for row in range(header_row, header_row + height):
                value = cls._text(raw.iat[row, col])
                if value and value not in parts:
                    parts.append(value)
            headers.append(" ".join(parts) or f"column_{col}")
        return headers

    @classmethod
    def _find_header_row(cls, raw: pd.DataFrame) -> int | None:
        best: tuple[int, int] | None = None
        for idx in range(min(len(raw), 30)):
            values = [cls._text(v) or "" for v in raw.iloc[idx].tolist()]
            score = sum(any(k in value for k in cls.HEADER_KEYWORDS) for value in values)
            if score >= 2 and (best is None or score > best[1]):
                best = (idx, score)
        return best[0] if best else None

    @classmethod
    def _find_col(cls, columns: Any, *needles: str) -> str | None:
        for column in columns:
            text = str(column)
            if any(needle in text for needle in needles):
                return column
        return None

    @classmethod
    def _parse_weight_range(cls, value: Any) -> tuple[float, float] | None:
        text = cls._text(value)
        if not text:
            return None
        nums = re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))
        if not nums:
            return None
        values = [float(n) for n in nums[:2]]
        return values[0], values[-1]

    @classmethod
    def _number(cls, value: Any) -> float | None:
        text = cls._text(value)
        if not text or text == "*":
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
        return float(match.group()) if match else None

    @classmethod
    def _weight_from_header(cls, header: str | None) -> float | None:
        if not header:
            return None
        match = re.search(r"(?:首|续)\s*(\d+(?:\.\d+)?)\s*KG", header)
        return float(match.group(1)) if match else None

    @classmethod
    def _infer_cargo_type(cls, channel: str | None, accepted: str | None, headers: str = "") -> str | None:
        """Infer cargo type while treating an explicit XLS cargo column as authoritative."""
        if accepted:
            explicit = accepted.strip()
            if "普货" in explicit and not any(term in explicit for term in ("带电", "纯电池", "液体", "膏体", "粉末")):
                return "普货"
            if explicit in {"P", "P货", "P服装", "仿牌", "敏货", "仿牌/敏货"}:
                return "P"
            if "纯电池" in explicit:
                return "纯电池"
            if "带电" in explicit:
                return "带电"
            if "液体" in explicit:
                return "液体"
            if "膏体" in explicit:
                return "膏体"
            if "粉末" in explicit:
                return "粉末"
            if "特货" in explicit:
                return "特货"

        text = f"{channel or ''} {accepted or ''} {headers}"
        if "纯电池" in text:
            return "纯电池"
        if "普货" in channel_or_empty(channel):
            return "普货"
        # XLS 中 P 统一表示仿牌/敏感货，不能再解释成“P服装”。
        if re.search(r"(?:^|[-_\s])P(?:$|[-_\s]|服装|货|敏感|仿牌)", text, re.IGNORECASE):
            return "P"
        if "P货" in text or "P服装" in text or "服装" in text:
            return "P"
        if "普货" in headers and "带电" not in channel_or_empty(channel):
            return "普货"
        if "不接带电" in text and "普货" in text:
            return "普货"
        if "带电" in text:
            return "带电"
        if "液体" in text:
            return "液体"
        if "膏体" in text:
            return "膏体"
        if "粉末" in text:
            return "粉末"
        if "特货" in text:
            return "特货"
        if "普货" in text:
            return "普货"
        return None

    def _build_country_catalog(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for sheet_name in self.sheet_names:
            raw = pd.read_excel(self._excel, sheet_name=sheet_name, header=None)
            for row in raw.itertuples(index=False, name=None):
                values = [self._text(value) for value in row]
                for idx, value in enumerate(values):
                    if not value:
                        continue
                    match = re.fullmatch(r"([A-Z]{2})", value.upper())
                    if not match:
                        continue
                    chinese = next((v for v in values[idx + 1:idx + 3] if v and re.search(r"[\u4e00-\u9fff]", v)), None)
                    english = next((v for v in values[idx + 1:idx + 3] if v and re.fullmatch(r"[A-Za-z][A-Za-z .'-]+", v)), None)
                    if chinese:
                        canonical = re.sub(r"\s+", "", chinese)
                        aliases[canonical] = canonical
                        if english:
                            aliases[english.strip().lower()] = canonical
                    break
        return aliases

    def _infer_country(self, sheet_name: str, channel: str | None) -> str | None:
        text = f"{channel or ''} {sheet_name}"
        for keyword, country in self.COUNTRY_COMPOSITE_SHEETS:
            if keyword in text:
                return country
        normalized = text.lower()
        matches: list[tuple[int, str]] = []
        for alias, country in self.country_catalog.items():
            if alias and alias in normalized:
                matches.append((len(alias), country))
        if not matches:
            return None
        matches.sort(reverse=True)
        return matches[0][1]

    @classmethod
    def _is_zone_table(cls, raw: pd.DataFrame, header_row: int) -> bool:
        row = " ".join(cls._text(v) or "" for v in raw.iloc[header_row].tolist())
        next_row = " ".join(cls._text(v) or "" for v in raw.iloc[header_row + 1].tolist()) if header_row + 1 < len(raw) else ""
        return ("区域" in row and "重量段" in row) or ("区域" in row and "重量段" in next_row)

    def _parse_zone_table(self, raw: pd.DataFrame, header_row: int, sheet_name: str) -> list[ChannelRate]:
        country_row = header_row + 1
        if country_row >= len(raw):
            return []
        countries = [self._text(v) for v in raw.iloc[country_row].tolist()]
        results: list[ChannelRate] = []
        for idx in range(country_row + 1, len(raw)):
            row = raw.iloc[idx]
            weight = self._parse_weight_range(row.iloc[1])
            if not weight:
                continue
            service_type = self._text(row.iloc[0])
            for col in range(2, raw.shape[1]):
                country = countries[col]
                if not country:
                    continue
                results.append(ChannelRate(sheet_name=sheet_name, channel_name=sheet_name, countries=country, cargo_type=self._infer_cargo_type(service_type, None), weight_min=weight[0], weight_max=weight[1], price_per_kg=self._number(row.iloc[col])))
        return results

    @staticmethod
    def _text(value: Any) -> str | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        text = str(value).strip()
        return text or None


def channel_or_empty(channel: str | None) -> str:
    return channel or ""
