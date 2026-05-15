from __future__ import annotations

from typing import Any, Dict, List


def _slugify(value: str) -> str:
    text = (value or "").strip().lower()
    out = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    slug = "".join(out)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


def _build_entry(
    *,
    name: str,
    province: str,
    municipality_type: str,
    source_url: str = "https://www.etenders.gov.za/",
    priority_tier: int,
    crawl_zone: str,
    crawl_interval_minutes: int,
    notes: str,
) -> Dict[str, Any]:
    return {
        "entity_name": name,
        "sphere": "municipal",
        "entity_type": "municipality",
        "municipality_type": municipality_type,
        "province": province,
        "source_key": f"municipality_{_slugify(name)}",
        "source_type": "mixed",
        "source_url": source_url,
        "priority_tier": priority_tier,
        "crawl_zone": crawl_zone,
        "crawl_interval_minutes": crawl_interval_minutes,
        "expected_submission_method": "mixed",
        "fit_supply_delivery": "high" if municipality_type == "metro" else "medium",
        "portal_health_status": "unknown",
        "is_active": True,
        "notes": notes,
    }


METRO_MUNICIPALITIES: List[Dict[str, str]] = [
    {"name": "Buffalo City Metropolitan Municipality", "province": "Eastern Cape"},
    {"name": "Nelson Mandela Bay Metropolitan Municipality", "province": "Eastern Cape"},
    {"name": "Mangaung Metropolitan Municipality", "province": "Free State"},
    {"name": "City of Ekurhuleni Metropolitan Municipality", "province": "Gauteng"},
    {"name": "City of Johannesburg Metropolitan Municipality", "province": "Gauteng"},
    {"name": "City of Tshwane Metropolitan Municipality", "province": "Gauteng"},
    {"name": "eThekwini Metropolitan Municipality", "province": "KwaZulu-Natal"},
    {"name": "City of Cape Town Metropolitan Municipality", "province": "Western Cape"},
]

DISTRICT_MUNICIPALITIES: List[Dict[str, str]] = [
    {"name": "Alfred Nzo District Municipality", "province": "Eastern Cape"},
    {"name": "Amathole District Municipality", "province": "Eastern Cape"},
    {"name": "Chris Hani District Municipality", "province": "Eastern Cape"},
    {"name": "Joe Gqabi District Municipality", "province": "Eastern Cape"},
    {"name": "OR Tambo District Municipality", "province": "Eastern Cape"},
    {"name": "Sarah Baartman District Municipality", "province": "Eastern Cape"},

    {"name": "Fezile Dabi District Municipality", "province": "Free State"},
    {"name": "Lejweleputswa District Municipality", "province": "Free State"},
    {"name": "Thabo Mofutsanyana District Municipality", "province": "Free State"},
    {"name": "Xhariep District Municipality", "province": "Free State"},

    {"name": "Sedibeng District Municipality", "province": "Gauteng"},
    {"name": "West Rand District Municipality", "province": "Gauteng"},

    {"name": "Amajuba District Municipality", "province": "KwaZulu-Natal"},
    {"name": "Harry Gwala District Municipality", "province": "KwaZulu-Natal"},
    {"name": "iLembe District Municipality", "province": "KwaZulu-Natal"},
    {"name": "King Cetshwayo District Municipality", "province": "KwaZulu-Natal"},
    {"name": "Ugu District Municipality", "province": "KwaZulu-Natal"},
    {"name": "uMgungundlovu District Municipality", "province": "KwaZulu-Natal"},
    {"name": "uMkhanyakude District Municipality", "province": "KwaZulu-Natal"},
    {"name": "uMzinyathi District Municipality", "province": "KwaZulu-Natal"},
    {"name": "uThukela District Municipality", "province": "KwaZulu-Natal"},
    {"name": "Zululand District Municipality", "province": "KwaZulu-Natal"},

    {"name": "Capricorn District Municipality", "province": "Limpopo"},
    {"name": "Mopani District Municipality", "province": "Limpopo"},
    {"name": "Sekhukhune District Municipality", "province": "Limpopo"},
    {"name": "Vhembe District Municipality", "province": "Limpopo"},
    {"name": "Waterberg District Municipality", "province": "Limpopo"},

    {"name": "Ehlanzeni District Municipality", "province": "Mpumalanga"},
    {"name": "Gert Sibande District Municipality", "province": "Mpumalanga"},
    {"name": "Nkangala District Municipality", "province": "Mpumalanga"},

    {"name": "Bojanala Platinum District Municipality", "province": "North West"},
    {"name": "Dr Kenneth Kaunda District Municipality", "province": "North West"},
    {"name": "Dr Ruth Segomotsi Mompati District Municipality", "province": "North West"},
    {"name": "Ngaka Modiri Molema District Municipality", "province": "North West"},

    {"name": "Frances Baard District Municipality", "province": "Northern Cape"},
    {"name": "John Taolo Gaetsewe District Municipality", "province": "Northern Cape"},
    {"name": "Namakwa District Municipality", "province": "Northern Cape"},
    {"name": "Pixley ka Seme District Municipality", "province": "Northern Cape"},
    {"name": "ZF Mgcawu District Municipality", "province": "Northern Cape"},

    {"name": "Cape Winelands District Municipality", "province": "Western Cape"},
    {"name": "Central Karoo District Municipality", "province": "Western Cape"},
    {"name": "Garden Route District Municipality", "province": "Western Cape"},
    {"name": "Overberg District Municipality", "province": "Western Cape"},
    {"name": "West Coast District Municipality", "province": "Western Cape"},
]

LOCAL_MUNICIPALITIES_BY_PROVINCE: Dict[str, List[str]] = {
    "Eastern Cape": [
        "Amahlathi Local Municipality",
        "Blue Crane Route Local Municipality",
        "Dr AB Xuma Local Municipality",
        "Dr Beyers Naude Local Municipality",
        "Elundini Local Municipality",
        "Emalahleni Local Municipality",
        "Enoch Mgijima Local Municipality",
        "Great Kei Local Municipality",
        "Ingquza Hill Local Municipality",
        "Intsika Yethu Local Municipality",
        "Inxuba Yethemba Local Municipality",
        "King Sabata Dalindyebo Local Municipality",
        "Kouga Local Municipality",
        "Koukamma Local Municipality",
        "Makana Local Municipality",
        "Matatiele Local Municipality",
        "Mbhashe Local Municipality",
        "Mhlontlo Local Municipality",
        "Mnquma Local Municipality",
        "Ndlambe Local Municipality",
        "Ngqushwa Local Municipality",
        "Ntabankulu Local Municipality",
        "Nyandeni Local Municipality",
        "Port St Johns Local Municipality",
        "Raymond Mhlaba Local Municipality",
        "Sakhisizwe Local Municipality",
        "Senqu Local Municipality",
        "Sundays River Valley Local Municipality",
        "Umzimvubu Local Municipality",
        "Walter Sisulu Local Municipality",
        "Winnie Madikizela-Mandela Local Municipality",
    ],
    "Free State": [
        "Dihlabeng Local Municipality",
        "Kopanong Local Municipality",
        "Letsemeng Local Municipality",
        "Mafube Local Municipality",
        "Maluti a Phofung Local Municipality",
        "Mantsopa Local Municipality",
        "Masilonyana Local Municipality",
        "Matjhabeng Local Municipality",
        "Metsimaholo Local Municipality",
        "Mohokare Local Municipality",
        "Moqhaka Local Municipality",
        "Nala Local Municipality",
        "Ngwathe Local Municipality",
        "Nketoana Local Municipality",
        "Phumelela Local Municipality",
        "Setsoto Local Municipality",
        "Tokologo Local Municipality",
        "Tswelopele Local Municipality",
    ],
    "Gauteng": [
        "Emfuleni Local Municipality",
        "Lesedi Local Municipality",
        "Merafong City Local Municipality",
        "Midvaal Local Municipality",
        "Mogale City Local Municipality",
        "Rand West City Local Municipality",
    ],
    "KwaZulu-Natal": [
        "AbaQulusi Local Municipality",
        "Alfred Duma Local Municipality",
        "Big 5 Hlabisa Local Municipality",
        "City of uMhlathuze Local Municipality",
        "Dannhauser Local Municipality",
        "Dr Nkosazana Dlamini Zuma Local Municipality",
        "eDumbe Local Municipality",
        "Emadlangeni Local Municipality",
        "Endumeni Local Municipality",
        "Greater Kokstad Local Municipality",
        "Impendle Local Municipality",
        "Inkosi Langalibalele Local Municipality",
        "Inkosi Mtubatuba Local Municipality",
        "Jozini Local Municipality",
        "KwaDukuza Local Municipality",
        "Mandeni Local Municipality",
        "Maphumulo Local Municipality",
        "Mkhambathini Local Municipality",
        "Mpofana Local Municipality",
        "Msunduzi Local Municipality",
        "Mthonjaneni Local Municipality",
        "Ndwedwe Local Municipality",
        "Newcastle Local Municipality",
        "Nkandla Local Municipality",
        "Nongoma Local Municipality",
        "Nquthu Local Municipality",
        "Okhahlamba Local Municipality",
        "Ray Nkonyeni Local Municipality",
        "Richmond Local Municipality",
        "Ulundi Local Municipality",
        "uMdoni Local Municipality",
        "uMfolozi Local Municipality",
        "uMhlabuyalingana Local Municipality",
        "uMlalazi Local Municipality",
        "uMngeni Local Municipality",
        "uMshwathi Local Municipality",
        "uMsinga Local Municipality",
        "Umuziwabantu Local Municipality",
        "Umvoti Local Municipality",
        "Umzimkhulu Local Municipality",
        "Umzumbe Local Municipality",
        "uPhongolo Local Municipality",
        "Johannes Phumani Phungula Local Municipality",
    ],
    "Limpopo": [
        "Ba-Phalaborwa Local Municipality",
        "Bela-Bela Local Municipality",
        "Blouberg Local Municipality",
        "Collins Chabane Local Municipality",
        "Elias Motsoaledi Local Municipality",
        "Ephraim Mogale Local Municipality",
        "Fetakgomo Tubatse Local Municipality",
        "Greater Giyani Local Municipality",
        "Greater Letaba Local Municipality",
        "Greater Tzaneen Local Municipality",
        "Lepelle-Nkumpi Local Municipality",
        "Lephalale Local Municipality",
        "Makhado Local Municipality",
        "Makhuduthamaga Local Municipality",
        "Maruleng Local Municipality",
        "Modimolle-Mookgophong Local Municipality",
        "Mogalakwena Local Municipality",
        "Molemole Local Municipality",
        "Musina Local Municipality",
        "Polokwane Local Municipality",
        "Thabazimbi Local Municipality",
        "Thulamela Local Municipality",
    ],
    "Mpumalanga": [
        "Bushbuckridge Local Municipality",
        "Chief Albert Luthuli Local Municipality",
        "City of Mbombela Local Municipality",
        "Dipaleseng Local Municipality",
        "Dr JS Moroka Local Municipality",
        "Emakhazeni Local Municipality",
        "Emalahleni Local Municipality",
        "Govan Mbeki Local Municipality",
        "Lekwa Local Municipality",
        "Mkhondo Local Municipality",
        "Msukaligwa Local Municipality",
        "Nkomazi Local Municipality",
        "Pixley ka Seme Local Municipality",
        "Steve Tshwete Local Municipality",
        "Thaba Chweu Local Municipality",
        "Thembisile Hani Local Municipality",
        "Victor Khanye Local Municipality",
    ],
    "North West": [
        "City of Matlosana Local Municipality",
        "Ditsobotla Local Municipality",
        "Greater Taung Local Municipality",
        "JB Marks Local Municipality",
        "Kagisano-Molopo Local Municipality",
        "Kgetlengrivier Local Municipality",
        "Lekwa-Teemane Local Municipality",
        "Madibeng Local Municipality",
        "Mahikeng Local Municipality",
        "Mamusa Local Municipality",
        "Maquassi Hills Local Municipality",
        "Moretele Local Municipality",
        "Moses Kotane Local Municipality",
        "Naledi Local Municipality",
        "Ramotshere Moiloa Local Municipality",
        "Ratlou Local Municipality",
        "Rustenburg Local Municipality",
        "Tswaing Local Municipality",
    ],
    "Northern Cape": [
        "!Kheis Local Municipality",
        "Dawid Kruiper Local Municipality",
        "Dikgatlong Local Municipality",
        "Emthanjeni Local Municipality",
        "Ga-Segonyana Local Municipality",
        "Gamagara Local Municipality",
        "Hantam Local Municipality",
        "Joe Morolong Local Municipality",
        "Kai !Garib Local Municipality",
        "Kamiesberg Local Municipality",
        "Kareeberg Local Municipality",
        "Karoo Hoogland Local Municipality",
        "Kgatelopele Local Municipality",
        "Khai-Ma Local Municipality",
        "Magareng Local Municipality",
        "Nama Khoi Local Municipality",
        "Phokwane Local Municipality",
        "Renosterberg Local Municipality",
        "Richtersveld Local Municipality",
        "Siyancuma Local Municipality",
        "Siyathemba Local Municipality",
        "Sol Plaatje Local Municipality",
        "Thembelihle Local Municipality",
        "Tsantsabane Local Municipality",
        "Ubuntu Local Municipality",
        "Umsobomvu Local Municipality",
    ],
    "Western Cape": [
        "Beaufort West Local Municipality",
        "Bergrivier Local Municipality",
        "Bitou Local Municipality",
        "Breede Valley Local Municipality",
        "Cape Agulhas Local Municipality",
        "Cederberg Local Municipality",
        "Drakenstein Local Municipality",
        "George Local Municipality",
        "Hessequa Local Municipality",
        "Kannaland Local Municipality",
        "Knysna Local Municipality",
        "Laingsburg Local Municipality",
        "Langeberg Local Municipality",
        "Matzikama Local Municipality",
        "Mossel Bay Local Municipality",
        "Oudtshoorn Local Municipality",
        "Overstrand Local Municipality",
        "Prince Albert Local Municipality",
        "Saldanha Bay Local Municipality",
        "Stellenbosch Local Municipality",
        "Swartland Local Municipality",
        "Swellendam Local Municipality",
        "Theewaterskloof Local Municipality",
        "Witzenberg Local Municipality",
    ],
}

EXPECTED_COUNTS = {
    "metros": 8,
    "districts": 44,
    "locals": 205,
    "total": 257,
}


def build_named_municipal_seed() -> List[Dict[str, Any]]:
    municipalities: List[Dict[str, Any]] = []

    for row in METRO_MUNICIPALITIES:
        interval = 20 if row["province"] in {"Free State", "Gauteng"} else 30
        municipalities.append(
            _build_entry(
                name=row["name"],
                province=row["province"],
                municipality_type="metro",
                priority_tier=4,
                crawl_zone="hot",
                crawl_interval_minutes=interval,
                notes="Named metro municipality. Start with eTender, then add direct SCM/tender site parser where available.",
            )
        )

    for row in DISTRICT_MUNICIPALITIES:
        municipalities.append(
            _build_entry(
                name=row["name"],
                province=row["province"],
                municipality_type="district",
                priority_tier=5,
                crawl_zone="warm",
                crawl_interval_minutes=90,
                notes="Named district municipality. Track via eTender and later direct district website parser where active.",
            )
        )

    for province, locals_list in LOCAL_MUNICIPALITIES_BY_PROVINCE.items():
        for name in locals_list:
            zone = "warm" if province in {"Free State", "Gauteng", "KwaZulu-Natal"} else "cold"
            interval = 90 if zone == "warm" else 240
            municipalities.append(
                _build_entry(
                    name=name,
                    province=province,
                    municipality_type="local",
                    priority_tier=6,
                    crawl_zone=zone,
                    crawl_interval_minutes=interval,
                    notes="Named local municipality. Start through eTender aggregation first, then attach direct website parser if the municipality has an active SCM/tenders page.",
                )
            )

    return municipalities


def build_municipal_summary() -> Dict[str, Any]:
    municipalities = build_named_municipal_seed()

    metros = [m for m in municipalities if m.get("municipality_type") == "metro"]
    districts = [m for m in municipalities if m.get("municipality_type") == "district"]
    locals_ = [m for m in municipalities if m.get("municipality_type") == "local"]

    by_province: Dict[str, Dict[str, int]] = {}
    for row in municipalities:
        province = row["province"]
        by_province.setdefault(province, {"metro": 0, "district": 0, "local": 0, "total": 0})
        by_province[province][row["municipality_type"]] += 1
        by_province[province]["total"] += 1

    return {
        "total_named_seed_entries": len(municipalities),
        "metros": len(metros),
        "districts": len(districts),
        "locals": len(locals_),
        "expected_counts": EXPECTED_COUNTS,
        "matches_expected": (
            len(metros) == EXPECTED_COUNTS["metros"]
            and len(districts) == EXPECTED_COUNTS["districts"]
            and len(locals_) == EXPECTED_COUNTS["locals"]
            and len(municipalities) == EXPECTED_COUNTS["total"]
        ),
        "by_province": by_province,
    }


LMCP_NAMED_MUNICIPAL_REGISTRY: Dict[str, Any] = {
    "version": "2026-03-30",
    "named_municipalities": build_named_municipal_seed(),
    "summary": build_municipal_summary(),
}


if __name__ == "__main__":
    import json
    print(json.dumps(LMCP_NAMED_MUNICIPAL_REGISTRY, indent=2))
