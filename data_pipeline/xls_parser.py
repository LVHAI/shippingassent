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


class XLSPipeline:
    HEADER_KEYWORDS = ("渠道", "国家", "重量", "运费", "首", "续", "类型", "区域")

    def __init__(self, xls_path: str | Path):
        self.xls_path = Path(xls_path)
        if not self.xls_path.is_file():
            raise FileNotFoundError(self.xls_path)
        self._excel = pd.ExcelFile(self.xls_path, engine="xlrd")
        self.sheet_names = self._excel.sheet_names

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

            results.append(ChannelRate(
                sheet_name=sheet_name,
                channel_name=channel,
                countries=country,
                cargo_type=cargo,
                weight_min=weight[0],
                weight_max=weight[1],
                price_per_kg=price,
                handling_fee=handling,
                first_weight=first_weight,
                first_weight_price=first_price,
                additional_weight=additional_weight,
                additional_weight_price=additional_price,
                size_requirements=self._text(row.get(size_col)) if size_col else None,
                transit_time=self._text(row.get(transit_col)) if transit_col else None,
                carrier=self._text(row.get(carrier_col)) if carrier_col else None,
            ))
        return results

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
        text = f"{channel or ''} {accepted or ''} {headers}"
        if "纯电池" in text:
            return "纯电池"
        if "P货" in text or "P服装" in text or "服装" in text:
            return "P货"
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

    @classmethod
    def _infer_country(cls, sheet_name: str, channel: str | None) -> str | None:
        text = f"{channel or ''} {sheet_name}"
        for country in ("美国", "日本", "巴西", "加拿大", "墨西哥", "澳洲", "英国", "欧洲"):
            if country in text:
                return country
        return None

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
                results.append(ChannelRate(
                    sheet_name=sheet_name,
                    channel_name=sheet_name,
                    countries=country,
                    cargo_type=self._infer_cargo_type(service_type, None),
                    weight_min=weight[0],
                    weight_max=weight[1],
                    price_per_kg=self._number(row.iloc[col]),
                ))
        return results

    @staticmethod
    def _text(value: Any) -> str | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        text = str(value).strip()
        return text or None
