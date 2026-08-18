from io import BytesIO
from decimal import Decimal
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.graphics.barcode.code128 import Code128
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _money(value) -> str:
    try:
        return f"${Decimal(str(value or 0)):,.2f}"
    except Exception:
        return "$0.00"


def _text(value, fallback="-") -> str:
    if value is None:
        return fallback
    value = str(value).strip()
    return value or fallback


def _p(value, style):
    return Paragraph(
        escape(_text(value)),
        style,
    )


def _ph(value, style):
    """
    Paragraph con markup simple de ReportLab (<b>, <i>, etc.).
    Los valores dinámicos deben escaparse antes de interpolarlos.
    """
    return Paragraph(
        _text(value),
        style,
    )


def _format_datetime(value) -> str:
    if not value:
        return "-"

    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return raw

    return dt.strftime("%d/%m/%Y %H:%M:%S")


def build_invoice_ride_pdf(
    *,
    invoice,
    workshop,
    settings,
    submission,
) -> bytes:
    """
    Genera la representación impresa (RIDE) de una factura ya autorizada.

    Sprint 3C mantiene este PDF deliberadamente simple y legible.
    La información tributaria proviene de la factura congelada,
    configuración SRI del taller y respuesta de autorización.
    """

    if not submission:
        raise ValueError("La factura todavía no fue enviada al SRI")

    auth_status = (
        submission.authorization_status
        or ""
    ).strip().upper()

    if auth_status not in {"AUTORIZADO", "AUT"}:
        raise ValueError(
            "El RIDE solo puede generarse para una factura autorizada"
        )

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"RIDE Factura {invoice.invoice_number}",
        author=_text(workshop.name, "SIADAUTO"),
    )

    styles = getSampleStyleSheet()

    title = ParagraphStyle(
        "RideTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        alignment=TA_CENTER,
        spaceAfter=4,
    )

    h2 = ParagraphStyle(
        "RideH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )

    body = ParagraphStyle(
        "RideBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.6,
        leading=9.4,
    )

    body_bold = ParagraphStyle(
        "RideBodyBold",
        parent=body,
        fontName="Helvetica-Bold",
    )

    small = ParagraphStyle(
        "RideSmall",
        parent=body,
        fontSize=6.6,
        leading=8,
        textColor=colors.HexColor("#334155"),
    )

    right = ParagraphStyle(
        "RideRight",
        parent=body,
        alignment=TA_RIGHT,
    )

    story = []

    issuer_name = (
        workshop.business_name
        or workshop.name
        or "Taller"
    )

    environment = (
        submission.authorization_environment
        or settings.environment
        or "PRUEBAS"
    )

    authorization_number = (
        submission.authorization_number
        or submission.access_key
    )


    workshop_name_html = escape(_text(workshop.name))
    workshop_address_html = escape(_text(workshop.address))
    workshop_ruc_html = escape(_text(workshop.ruc))
    invoice_number_html = escape(_text(invoice.invoice_number))
    authorization_number_html = escape(_text(authorization_number))
    environment_html = escape(_text(environment).upper())
    client_name_html = escape(_text(invoice.client_name))
    client_identification_html = escape(_text(invoice.client_identification))
    issue_date_html = escape(_text(invoice.issue_date))
    client_address_html = escape(_text(invoice.client_address))
    client_email_html = escape(_text(invoice.client_email))
    workshop_phone_html = escape(_text(workshop.phone))
    workshop_email_html = escape(_text(workshop.email))
    auth_date_html = escape(_format_datetime(submission.authorization_date))

    # --------------------------------------------------------
    # Encabezado en dos columnas
    # --------------------------------------------------------
    issuer_box = [
        _p(issuer_name, title),
        _ph(
            f"<b>Nombre comercial:</b> {workshop_name_html}",
            body,
        ),
        _ph(
            f"<b>Dirección matriz:</b> {workshop_address_html}",
            body,
        ),
    ]

    if getattr(settings, "special_taxpayer_code", None):
        issuer_box.append(
            _ph(
                "<b>Contribuyente especial:</b> "
                f"{escape(str(settings.special_taxpayer_code))}",
                body,
            )
        )

    issuer_box.append(
        _ph(
            "<b>Obligado a llevar contabilidad:</b> "
            f"{'SI' if settings.accounting_required else 'NO'}",
            body,
        )
    )

    if getattr(settings, "rimpe_type", None):
        issuer_box.append(
            _ph(
                f"<b>Régimen:</b> {escape(str(settings.rimpe_type))}",
                body,
            )
        )

    fiscal_box = [
        _ph(f"<b>R.U.C.:</b> {workshop_ruc_html}", body_bold),
        _ph("<b>FACTURA</b>", h2),
        _ph(
            f"<b>No.</b> {invoice_number_html}",
            body_bold,
        ),
        _ph("<b>NÚMERO DE AUTORIZACIÓN</b>", small),
        _p(authorization_number, small),
        _ph(
            "<b>FECHA DE AUTORIZACIÓN:</b> "
            f"{auth_date_html}",
            body,
        ),
        _ph(
            f"<b>AMBIENTE:</b> {environment_html}",
            body,
        ),
        _ph("<b>EMISIÓN:</b> NORMAL", body),
    ]

    header = Table(
        [[issuer_box, fiscal_box]],
        colWidths=[91 * mm, 91 * mm],
        hAlign="CENTER",
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (0, 0), 0.8, colors.HexColor("#475569")),
                ("BOX", (1, 0), (1, 0), 0.8, colors.HexColor("#475569")),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 4 * mm))

    # --------------------------------------------------------
    # Clave de acceso + código de barras
    # --------------------------------------------------------
    access_key = _text(submission.access_key)

    barcode = Code128(
        access_key,
        barHeight=11 * mm,
        barWidth=0.27 * mm,
        humanReadable=False,
    )

    barcode_box = Table(
        [
            [_ph("<b>CLAVE DE ACCESO</b>", small)],
            [barcode],
            [_p(access_key, small)],
        ],
        colWidths=[182 * mm],
    )
    barcode_box.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#94A3B8")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    story.append(barcode_box)
    story.append(Spacer(1, 4 * mm))

    # --------------------------------------------------------
    # Cliente
    # --------------------------------------------------------
    customer_rows = [
        [
            _ph(
                f"<b>Razón social / Nombres:</b> "
                f"{client_name_html}",
                body,
            ),
            _ph(
                f"<b>Identificación:</b> "
                f"{client_identification_html}",
                body,
            ),
        ],
        [
            _ph(
                f"<b>Fecha emisión:</b> {issue_date_html}",
                body,
            ),
            _ph(
                f"<b>Dirección:</b> {client_address_html}",
                body,
            ),
        ],
        [
            _ph(
                f"<b>Email:</b> {client_email_html}",
                body,
            ),
            "",
        ],
    ]

    customer = Table(
        customer_rows,
        colWidths=[91 * mm, 91 * mm],
    )
    customer.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#94A3B8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    story.append(customer)
    story.append(Spacer(1, 4 * mm))

    # --------------------------------------------------------
    # Detalle
    # --------------------------------------------------------
    detail_data = [
        [
            _ph("<b>Cant.</b>", small),
            _ph("<b>Descripción</b>", small),
            _ph("<b>P. Unit.</b>", small),
            _ph("<b>Descuento</b>", small),
            _ph("<b>IVA</b>", small),
            _ph("<b>Total</b>", small),
        ]
    ]

    for item in invoice.items:
        detail_data.append(
            [
                _p(f"{Decimal(str(item.quantity or 0)):.2f}", body),
                _p(item.description, body),
                _p(_money(item.unit_price), right),
                _p(_money(item.discount), right),
                _p(_money(item.tax_amount), right),
                _p(_money(item.total), right),
            ]
        )

    detail = Table(
        detail_data,
        colWidths=[
            15 * mm,
            76 * mm,
            24 * mm,
            22 * mm,
            20 * mm,
            25 * mm,
        ],
        repeatRows=1,
    )
    detail.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#64748B")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(detail)
    story.append(Spacer(1, 4 * mm))

    # --------------------------------------------------------
    # Información adicional + totales
    # --------------------------------------------------------
    additional = [
        _ph("<b>Información adicional</b>", h2),
        _ph(f"<b>Teléfono:</b> {workshop_phone_html}", body),
        _ph(f"<b>Email:</b> {workshop_email_html}", body),
    ]

    if getattr(workshop, "footer_text", None):
        additional.append(
            _p(workshop.footer_text, small)
        )

    totals = [
        [_p("Subtotal tarifa 0%", body), _p(_money(invoice.subtotal_0), right)],
        [_p("Subtotal gravado", body), _p(_money(invoice.subtotal_taxed), right)],
        [_p("Descuento", body), _p(_money(invoice.discount), right)],
        [_p("IVA", body), _p(_money(invoice.tax_amount), right)],
        [_ph("<b>VALOR TOTAL</b>", body_bold), _ph(f"<b>{escape(_money(invoice.total))}</b>", right)],
    ]

    totals_table = Table(
        totals,
        colWidths=[47 * mm, 30 * mm],
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#64748B")),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    bottom = Table(
        [[additional, totals_table]],
        colWidths=[101 * mm, 81 * mm],
    )
    bottom.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (0, 0), 0.5, colors.HexColor("#64748B")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(KeepTogether(bottom))
    story.append(Spacer(1, 5 * mm))

    story.append(
        _p(
            "RIDE - Representación Impresa del Documento Electrónico. "
            "La información de autorización corresponde a la respuesta del SRI.",
            small,
        )
    )

    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()
    return pdf
