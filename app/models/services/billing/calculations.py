from decimal import Decimal, ROUND_HALF_UP


MONEY_QUANTIZER = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(
        MONEY_QUANTIZER,
        rounding=ROUND_HALF_UP,
    )


def calculate_invoice_item(
    quantity,
    unit_price,
    tax_rate,
    discount=0,
) -> dict:
    quantity = Decimal(str(quantity or 0))
    unit_price = money(unit_price)
    discount = money(discount)
    tax_rate = Decimal(str(tax_rate or 0))

    gross_subtotal = money(quantity * unit_price)

    if discount > gross_subtotal:
        discount = gross_subtotal

    subtotal = money(gross_subtotal - discount)

    tax_amount = money(
        subtotal * (tax_rate / Decimal("100"))
    )

    total = money(subtotal + tax_amount)

    return {
        "quantity": quantity,
        "unit_price": unit_price,
        "discount": discount,
        "subtotal": subtotal,
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "total": total,
    }