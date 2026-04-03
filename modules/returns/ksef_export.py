"""
KSeF (Krajowy System e-Faktur) correction invoice exporter.

Generates FA(2) correction invoice data for finalized returns.
Supports JSON (for API) and XML (for direct KSeF submission).

KSeF schema reference: https://www.podatki.gov.pl/ksef/
Correction invoice = Faktura korygująca (§ 106j UoVAT)

Flow:
  1. Return finalized → Return_Finalized event
  2. KSeFExporter.build_correction() → dict payload
  3. POST to ERP system (or directly to KSeF API in prod)
  4. ERP returns ksef_reference_number
  5. Worker polls ERP → updates returns.ksef_reference
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

VAT_RATE_MAP = {
    Decimal("0.23"): "A",   # 23% — standard
    Decimal("0.08"): "B",   # 8%
    Decimal("0.05"): "C",   # 5%
    Decimal("0.00"): "E",   # 0% (ZW)
}


class KSeFExporter:

    def build_correction(
        self,
        return_obj: Any,
        order: Any,
        return_items: list[Any],
        order_items_map: dict[str, Any],   # order_item_id → OrderItem
        seller: dict,                       # {name, nip, address}
    ) -> dict:
        """
        Build FA(2) correction invoice payload (JSON).

        Returns a dict compatible with KSeF FA_VAT(2) schema.
        Can be submitted directly or converted to XML.
        """
        items = []
        total_net_correction = Decimal("0")
        total_vat_correction = Decimal("0")
        total_gross_correction = Decimal("0")

        for ri in return_items:
            oi = order_items_map.get(str(ri.order_item_id))
            if not oi:
                continue

            qty = ri.quantity_accepted if ri.quantity_accepted is not None else ri.quantity_requested
            unit_net = (oi.unit_price_net or oi.unit_price_gross) * -1
            vat_rate = Decimal(str(oi.vat_rate or "0.23"))
            unit_vat = (unit_net * vat_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
            unit_gross = unit_net + unit_vat

            line_net = (unit_net * qty).quantize(Decimal("0.01"), ROUND_HALF_UP)
            line_vat = (unit_vat * qty).quantize(Decimal("0.01"), ROUND_HALF_UP)
            line_gross = (unit_gross * qty).quantize(Decimal("0.01"), ROUND_HALF_UP)

            total_net_correction += line_net
            total_vat_correction += line_vat
            total_gross_correction += line_gross

            items.append({
                "NrWiersza": len(items) + 1,
                "P_7": oi.name,
                "P_8A": "szt.",
                "P_8B": str(qty),
                "P_9A": str(unit_net.quantize(Decimal("0.0001"), ROUND_HALF_UP)),
                "P_11": str(line_net),
                "P_12": VAT_RATE_MAP.get(vat_rate, "A"),
                "P_14_3": str(line_vat),
            })

        today = date.today().isoformat()
        invoice_number = f"KOR/{return_obj.rma_number}/{today.replace('-', '')}"

        return {
            "Fa": {
                "KodFormularza": {
                    "kodSystemowy": "FA (2)",
                    "wersjaSchemy": "1-0E"
                },
                "WariantFormularza": 2,
                "DataWytworzeniaFa": datetime.now(timezone.utc).isoformat(),
                "NrFaKorygowanej": order.invoice_ref or f"FV/{order.order_number}",
                "OkresFaKorygowanej": {
                    "DataOd": order.ordered_at.date().isoformat() if order.ordered_at else today,
                    "DataDo": today,
                },
                "PrzyczynaKorekty": self._map_reason(return_obj),
                "NrFa": invoice_number,
                "DataWystawienia": today,
                "DataSprzedazy": today,
                "RodzajFaktury": "KOR",
                "Podmiot1": {
                    "DaneIdentyfikacyjne": {
                        "NIP": seller["nip"],
                        "Nazwa": seller["name"],
                    },
                    "Adres": {
                        "AdresL1": seller.get("address", ""),
                    },
                },
                "Fa": {
                    "FaWiersz": items,
                    "P_15": str(total_gross_correction.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                },
                "Rozliczenie": {
                    "Obciazenia": [],
                    "Odliczenia": [],
                    "SumaNetto": [{
                        "P_13_1": str(total_net_correction.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                        "P_14_1": str(total_vat_correction.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                    }],
                    "P_15": str(total_gross_correction.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                },
                "_meta": {
                    "reverseos_return_id": str(return_obj.id),
                    "rma_number": return_obj.rma_number,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        }

    def to_xml(self, payload: dict) -> str:
        """Convert JSON payload to KSeF-compatible XML string."""
        fa = payload["Fa"]

        root = ET.Element("Faktura", {
            "xmlns": "http://crd.gov.pl/wzor/2023/06/29/12648/",
            "xmlns:etd": "http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2022/09/13/eD/DefinicjeTypy/",
        })

        # Nagłówek
        nagl = ET.SubElement(root, "Naglowek")
        ET.SubElement(nagl, "KodFormularza", kodSystemowy="FA (2)", wersjaSchemy="1-0E").text = "FA"
        ET.SubElement(nagl, "WariantFormularza").text = "2"
        ET.SubElement(nagl, "DataWytworzeniaFa").text = fa["DataWytworzeniaFa"]
        ET.SubElement(nagl, "NrFa").text = fa["NrFa"]
        ET.SubElement(nagl, "RodzajFaktury").text = "KOR"
        ET.SubElement(nagl, "NrFaKorygowanej").text = fa["NrFaKorygowanej"]
        ET.SubElement(nagl, "PrzyczynaKorekty").text = fa["PrzyczynaKorekty"]

        # Podmiot1
        p1 = ET.SubElement(root, "Podmiot1")
        di = ET.SubElement(p1, "DaneIdentyfikacyjne")
        ET.SubElement(di, "NIP").text = fa["Podmiot1"]["DaneIdentyfikacyjne"]["NIP"]
        ET.SubElement(di, "Nazwa").text = fa["Podmiot1"]["DaneIdentyfikacyjne"]["Nazwa"]

        # Fa wiersze
        fa_el = ET.SubElement(root, "Fa")
        for wiersz in fa["Fa"]["FaWiersz"]:
            w = ET.SubElement(fa_el, "FaWiersz")
            for k, v in wiersz.items():
                ET.SubElement(w, k).text = str(v)

        ET.SubElement(fa_el, "P_15").text = fa["Fa"]["P_15"]

        ET.indent(root, space="  ")
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")

    @staticmethod
    def _map_reason(return_obj: Any) -> str:
        reasons = {
            "damaged_in_transit":  "Towar uszkodzony w transporcie",
            "wrong_item_sent":     "Wysłano błędny towar",
            "not_as_described":    "Towar niezgodny z opisem",
            "defective":           "Towar wadliwy",
            "changed_mind":        "Odstąpienie od umowy w terminie ustawowym",
        }
        # Take first item reason if available
        if return_obj.items:
            reason = getattr(return_obj.items[0], "reason", "other")
            return reasons.get(reason, "Zwrot towaru")
        return "Zwrot towaru"


ksef_exporter = KSeFExporter()
