from typing import List

from sqlalchemy.orm import Session

from app.models import QuoteDraft, QuoteLineItem


def round2(value: float) -> float:
    return round(float(value or 0.0), 2)


def recalc_quote_totals(db: Session, quote: QuoteDraft) -> QuoteDraft:
    line_items: List[QuoteLineItem] = (
        db.query(QuoteLineItem)
        .filter(QuoteLineItem.quote_id == quote.id)
        .order_by(QuoteLineItem.line_no.asc(), QuoteLineItem.id.asc())
        .all()
    )

    base_cost = 0.0
    sell_price_ex_vat = 0.0

    for line in line_items:
        quantity = float(line.quantity or 0.0)
        unit_cost = float(line.unit_cost or 0.0)
        markup_pct = float(line.markup_pct or 0.0)

        unit_sell_price = round2(unit_cost * (1 + markup_pct / 100.0))
        line_total_ex_vat = round2(quantity * unit_sell_price)

        line.unit_sell_price = unit_sell_price
        line.line_total_ex_vat = line_total_ex_vat

        base_cost += quantity * unit_cost
        sell_price_ex_vat += line_total_ex_vat

        db.add(line)

    quote.base_cost = round2(base_cost)
    quote.sell_price_ex_vat = round2(sell_price_ex_vat)
    quote.vat_amount = round2(quote.sell_price_ex_vat * (quote.vat_pct / 100.0))
    quote.total_price_inc_vat = round2(quote.sell_price_ex_vat + quote.vat_amount)

    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def next_line_no(db: Session, quote_id: int) -> int:
    items = (
        db.query(QuoteLineItem)
        .filter(QuoteLineItem.quote_id == quote_id)
        .order_by(QuoteLineItem.line_no.desc(), QuoteLineItem.id.desc())
        .all()
    )
    if not items:
        return 1
    return int(items[0].line_no) + 1


def renumber_quote_lines(db: Session, quote_id: int) -> None:
    items = (
        db.query(QuoteLineItem)
        .filter(QuoteLineItem.quote_id == quote_id)
        .order_by(QuoteLineItem.line_no.asc(), QuoteLineItem.id.asc())
        .all()
    )
    for idx, item in enumerate(items, start=1):
        item.line_no = idx
        db.add(item)
    db.commit()
