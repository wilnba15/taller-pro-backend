from io import BytesIO
from decimal import Decimal
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

    # --------------------------------------------------------
    # Encabezado en dos columnas
    # --------------------------------------------------------
    issuer_box = [
        _p(issuer_name, title),
        _p(
            f"<b>Nombre comercial:</b> {_text(workshop.name)}",
            body,
        ),
        _p(
            f"<b>Dirección matriz:</b> {_text(workshop.address)}",
            body,
        ),
    ]

    if getattr(settings, "special_taxpayer_code", None):
        issuer_box.append(
            _p(
                "<b>Contribuyente especial:</b> "
                f"{settings.special_taxpayer_code}",
                body,
            )
        )

    issuer_box.append(
        _p(
            "<b>Obligado a llevar contabilidad:</b> "
            f"{'SI' if settings.accounting_required else 'NO'}",
            body,
        )
    )

    if getattr(settings, "rimpe_type", None):
        issuer_box.append(
            _p(
                f"<b>Régimen:</b> {settings.rimpe_type}",
                body,
            )
        )

    fiscal_box = [
        _p(f"<b>R.U.C.:</b> {_text(workshop.ruc)}", body_bold),
        _p("<b>FACTURA</b>", h2),
        _p(
            f"<b>No.</b> {_text(invoice.invoice_number)}",
            body_bold,
        ),
        _p("<b>NÚMERO DE AUTORIZACIÓN</b>", small),
        _p(authorization_number, small),
        _p(
            "<b>FECHA DE AUTORIZACIÓN:</b> "
            f"{_text(submission.authorization_date)}",
            body,
        ),
        _p(
            f"<b>AMBIENTE:</b> {_text(environment).upper()}",
            body,
        ),
        _p("<b>EMISIÓN:</b> NORMAL", body),
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
            [_p("<b>CLAVE DE ACCESO</b>", small)],
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
            _p(
                f"<b>Razón social / Nombres:</b> "
                f"{_text(invoice.client_name)}",
                body,
            ),
            _p(
                f"<b>Identificación:</b> "
                f"{_text(invoice.client_identification)}",
                body,
            ),
        ],
        [
            _p(
                f"<b>Fecha emisión:</b> {_text(invoice.issue_date)}",
                body,
            ),
            _p(
                f"<b>Dirección:</b> {_text(invoice.client_address)}",
                body,
            ),
        ],
        [
            _p(
                f"<b>Email:</b> {_text(invoice.client_email)}",
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
            _p("<b>Cant.</b>", small),
            _p("<b>Descripción</b>", small),
            _p("<b>P. Unit.</b>", small),
            _p("<b>Descuento</b>", small),
            _p("<b>IVA</b>", small),
            _p("<b>Total</b>", small),
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
        _p("<b>Información adicional</b>", h2),
        _p(f"<b>Teléfono:</b> {_text(workshop.phone)}", body),
        _p(f"<b>Email:</b> {_text(workshop.email)}", body),
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
        [_p("<b>VALOR TOTAL</b>", body_bold), _p(f"<b>{_money(invoice.total)}</b>", right)],
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
