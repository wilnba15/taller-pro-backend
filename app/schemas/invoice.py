from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class InvoiceItemResponse(BaseModel):
    id: int
    invoice_id: int

    item_type: str
    description: str

    quantity: Decimal
    unit_price: Decimal
    discount: Decimal

    subtotal: Decimal

    tax_rate: Decimal
    tax_amount: Decimal

    total: Decimal

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    id: int

    workshop_id: int
    work_order_id: int
    client_id: int

    establishment_code: str
    emission_point_code: str
    sequential: int

    invoice_number: str
    issue_date: date

    client_name: str
    client_identification: str
    client_email: str | None
    client_address: str | None

    subtotal_0: Decimal
    subtotal_taxed: Decimal
    tax_amount: Decimal
    discount: Decimal
    total: Decimal

    status: str

    created_at: datetime
    updated_at: datetime

    items: list[InvoiceItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class SriSettingResponse(BaseModel):
    id: int
    workshop_id: int

    environment: str

    establishment_code: str
    emission_point_code: str

    invoice_sequence: int

    default_tax_rate: Decimal

    accounting_required: bool

    special_taxpayer_code: str | None
    rimpe_type: str | None

    model_config = ConfigDict(from_attributes=True)