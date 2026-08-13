from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from xml.etree import ElementTree as ET

from app.models.invoice import Invoice
from app.models.sri_setting import SriSetting
from app.models.workshop import Workshop
from app.services.sri.access_key import sri_environment_code

MONEY = Decimal("0.01")


def decimal_money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def money_text(value) -> str:
    return f"{decimal_money(value):.2f}"


def quantity_text(value) -> str:
    amount = Decimal(str(value or 0))
    text = format(amount.normalize(), "f")
    return text if "." in text else f"{text}.00"


def tax_percentage_code(tax_rate) -> str:
    rate = decimal_money(tax_rate)
    mapping = {
        Decimal("0.00"): "0",
        Decimal("5.00"): "5",
        Decimal("12.00"): "2",
        Decimal("13.00"): "10",
        Decimal("14.00"): "3",
        Decimal("15.00"): "4",
    }
    if rate not in mapping:
        raise ValueError(f"Tarifa IVA {rate}% no soportada todavía por SIADAUTO Sprint 2A")
    return mapping[rate]


def buyer_identification_type(identification: str) -> str:
    value = (identification or "").strip()
    if value == "9999999999999":
        return "07"
    if value.isdigit() and len(value) == 13:
        return "04"
    if value.isdigit() and len(value) == 10:
        return "05"
    return "06"


def add_text(parent, tag: str, value) -> ET.Element:
    node = ET.SubElement(parent, tag)
    node.text = str(value)
    return node


def build_invoice_xml(*, invoice: Invoice, workshop: Workshop, settings: SriSetting, access_key: str) -> str:
    if not invoice.items:
        raise ValueError("La factura no tiene ítems")
    if not workshop.ruc:
        raise ValueError("El taller no tiene RUC registrado")

    legal_name = workshop.business_name or workshop.name or "SIADAUTO"
    commercial_name = workshop.name if workshop.name and workshop.name != legal_name else None
    matrix_address = workshop.address or "DIRECCION NO REGISTRADA"

    root = ET.Element("factura", {"id": "comprobante", "version": "2.1.0"})

    info_tributaria = ET.SubElement(root, "infoTributaria")
    add_text(info_tributaria, "ambiente", sri_environment_code(settings.environment))
    add_text(info_tributaria, "tipoEmision", "1")
    add_text(info_tributaria, "razonSocial", legal_name)
    if commercial_name:
        add_text(info_tributaria, "nombreComercial", commercial_name)
    add_text(info_tributaria, "ruc", workshop.ruc)
    add_text(info_tributaria, "claveAcceso", access_key)
    add_text(info_tributaria, "codDoc", "01")
    add_text(info_tributaria, "estab", str(invoice.establishment_code).zfill(3))
    add_text(info_tributaria, "ptoEmi", str(invoice.emission_point_code).zfill(3))
    add_text(info_tributaria, "secuencial", str(invoice.sequential).zfill(9))
    add_text(info_tributaria, "dirMatriz", matrix_address)

    info_factura = ET.SubElement(root, "infoFactura")
    add_text(info_factura, "fechaEmision", invoice.issue_date.strftime("%d/%m/%Y"))
    add_text(info_factura, "dirEstablecimiento", workshop.address or matrix_address)
    if settings.special_taxpayer_code:
        add_text(info_factura, "contribuyenteEspecial", settings.special_taxpayer_code)
    add_text(info_factura, "obligadoContabilidad", "SI" if settings.accounting_required else "NO")
    add_text(info_factura, "tipoIdentificacionComprador", buyer_identification_type(invoice.client_identification))
    add_text(info_factura, "razonSocialComprador", invoice.client_name)
    add_text(info_factura, "identificacionComprador", invoice.client_identification)
    if invoice.client_address:
        add_text(info_factura, "direccionComprador", invoice.client_address)

    total_without_taxes = decimal_money(invoice.subtotal_0) + decimal_money(invoice.subtotal_taxed)
    add_text(info_factura, "totalSinImpuestos", money_text(total_without_taxes))
    add_text(info_factura, "totalDescuento", money_text(invoice.discount))

    tax_groups = defaultdict(lambda: {"base": Decimal("0.00"), "tax": Decimal("0.00")})
    for item in invoice.items:
        rate = decimal_money(item.tax_rate)
        tax_groups[rate]["base"] += decimal_money(item.subtotal)
        tax_groups[rate]["tax"] += decimal_money(item.tax_amount)

    total_taxes = ET.SubElement(info_factura, "totalConImpuestos")
    for rate in sorted(tax_groups):
        data = tax_groups[rate]
        total_tax = ET.SubElement(total_taxes, "totalImpuesto")
        add_text(total_tax, "codigo", "2")
        add_text(total_tax, "codigoPorcentaje", tax_percentage_code(rate))
        add_text(total_tax, "baseImponible", money_text(data["base"]))
        add_text(total_tax, "valor", money_text(data["tax"]))

    add_text(info_factura, "propina", "0.00")
    add_text(info_factura, "importeTotal", money_text(invoice.total))
    add_text(info_factura, "moneda", "DOLAR")

    pagos = ET.SubElement(info_factura, "pagos")
    pago = ET.SubElement(pagos, "pago")
    add_text(pago, "formaPago", "01")
    add_text(pago, "total", money_text(invoice.total))

    detalles = ET.SubElement(root, "detalles")
    for index, item in enumerate(invoice.items, start=1):
        detalle = ET.SubElement(detalles, "detalle")
        add_text(detalle, "codigoPrincipal", f"ITEM{index:06d}")
        add_text(detalle, "descripcion", item.description[:300])
        add_text(detalle, "cantidad", quantity_text(item.quantity))
        add_text(detalle, "precioUnitario", money_text(item.unit_price))
        add_text(detalle, "descuento", money_text(item.discount))
        add_text(detalle, "precioTotalSinImpuesto", money_text(item.subtotal))

        impuestos = ET.SubElement(detalle, "impuestos")
        impuesto = ET.SubElement(impuestos, "impuesto")
        add_text(impuesto, "codigo", "2")
        add_text(impuesto, "codigoPorcentaje", tax_percentage_code(item.tax_rate))
        add_text(impuesto, "tarifa", money_text(item.tax_rate))
        add_text(impuesto, "baseImponible", money_text(item.subtotal))
        add_text(impuesto, "valor", money_text(item.tax_amount))

    additional_values = []
    if invoice.client_email:
        additional_values.append(("Email", invoice.client_email))
    if invoice.client_address:
        additional_values.append(("Direccion", invoice.client_address))

    if additional_values:
        info_adicional = ET.SubElement(root, "infoAdicional")
        for name, value in additional_values:
            field = ET.SubElement(info_adicional, "campoAdicional", {"nombre": name})
            field.text = str(value)[:300]

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")
