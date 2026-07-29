from datetime import date, timedelta, datetime
from decimal import Decimal
from io import BytesIO
from html import escape
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.database import get_db
from app.models.user import User
from app.core.security import get_current_user

router = APIRouter(
    prefix="/api/vehicle-life",
    tags=["SIADAUTO - Vida del Auto"],
)


def row_to_dict(row):
    return dict(row._mapping)


def money(value) -> str:
    try:
        return f"${Decimal(value or 0):,.2f}"
    except Exception:
        return "$0.00"


def km_text(value) -> str:
    try:
        return f"{int(value):,} km".replace(",", ".")
    except Exception:
        return "-"


def safe(value, fallback="-") -> str:
    if value in [None, ""]:
        return fallback
    return str(value)


def paragraph_text(value, fallback="-") -> str:
    return escape(safe(value, fallback))


MONTHS_ES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def long_date_es(value) -> str:
    if not value:
        return "Sin fecha"

    try:
        if isinstance(value, datetime):
            parsed = value.date()
        elif isinstance(value, date):
            parsed = value
        else:
            parsed = datetime.strptime(str(value)[:10], "%Y-%m-%d").date()

        return f"{parsed.day} de {MONTHS_ES[parsed.month]} de {parsed.year}"
    except Exception:
        return safe(value, "Sin fecha")


def load_remote_logo(logo_url: str | None):
    if not logo_url:
        return None

    try:
        request = Request(
            logo_url,
            headers={"User-Agent": "SIADAUTO/1.0"},
        )
        with urlopen(request, timeout=8) as response:
            content = response.read()

        if not content:
            return None

        image = Image(BytesIO(content))
        image._restrictSize(4.2 * cm, 2.6 * cm)
        return image
    except Exception:
        return None


def service_type_label(value) -> str:
    if value == "mano_obra":
        return "Mano de obra"
    if value == "repuesto":
        return "Repuesto"
    return safe(value, "Servicio")


def get_vehicle_life_rows(vehicle_id: int, workshop_id: int, db: Session):
    query = text("""
        SELECT
            wo.id AS work_order_id,
            COALESCE(wo.order_number, wo.id) AS order_number,
            COALESCE(wo.entry_date, CAST(wo.created_at AS DATE)) AS work_order_date,
            wo.current_km,
            wo.status,
            wo.workshop_id,
            wo.client_id,
            wo.vehicle_id,

            woi.id AS item_id,
            woi.item_type,
            woi.description,
            woi.quantity,
            woi.unit_price,
            woi.subtotal,
            woi.next_service_km,
            woi.next_service_date,
            woi.reminder_enabled,
            woi.reminder_sent

        FROM work_orders wo
        INNER JOIN work_order_items woi
            ON woi.work_order_id = wo.id
        WHERE wo.vehicle_id = :vehicle_id
          AND wo.workshop_id = :workshop_id
        ORDER BY
            wo.current_km DESC NULLS LAST,
            wo.entry_date DESC NULLS LAST,
            wo.id DESC,
            woi.id ASC
    """)

    rows = db.execute(
        query,
        {"vehicle_id": vehicle_id, "workshop_id": workshop_id},
    ).fetchall()

    return [row_to_dict(row) for row in rows]


def get_vehicle_header(vehicle_id: int, workshop_id: int, db: Session):
    query = text("""
        SELECT
            v.id AS vehicle_id,
            v.plate,
            v.brand,
            v.model,
            c.full_name AS client_name,
            c.phone AS client_phone,
            w.id AS workshop_id,
            w.name AS workshop_name,
            w.business_name AS workshop_business_name,
            w.ruc AS workshop_ruc,
            w.phone AS workshop_phone,
            w.email AS workshop_email,
            w.address AS workshop_address,
            w.logo_url AS workshop_logo_url,
            w.footer_text AS workshop_footer_text
        FROM vehicles v
        LEFT JOIN clients c
            ON c.id = v.client_id
           AND c.workshop_id = v.workshop_id
        LEFT JOIN workshops w
            ON w.id = v.workshop_id
        WHERE v.id = :vehicle_id
          AND v.workshop_id = :workshop_id
    """)

    row = db.execute(
        query,
        {"vehicle_id": vehicle_id, "workshop_id": workshop_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado para este taller")

    return dict(row)


@router.get("/vehicle/{vehicle_id}")
def get_vehicle_life(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = get_vehicle_life_rows(vehicle_id, current_user.workshop_id, db)

    total_invested = sum(float(row.get("subtotal") or 0) for row in rows)

    next_services = []
    for row in rows:
        if row.get("next_service_km") or row.get("next_service_date"):
            next_services.append({
                "work_order_id": row.get("work_order_id"),
                "order_number": row.get("order_number"),
                "item_id": row.get("item_id"),
                "description": row.get("description"),
                "item_type": row.get("item_type"),
                "current_km": row.get("current_km"),
                "next_service_km": row.get("next_service_km"),
                "next_service_date": row.get("next_service_date"),
                "reminder_enabled": row.get("reminder_enabled"),
                "reminder_sent": row.get("reminder_sent"),
            })

    return {
        "vehicle_id": vehicle_id,
        "total_events": len(rows),
        "total_invested": total_invested,
        "last_km": rows[0].get("current_km") if rows else None,
        "items": rows,
        "next_services": next_services,
    }


@router.get("/vehicle/{vehicle_id}/pdf")
def generate_vehicle_life_pdf(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    header = get_vehicle_header(vehicle_id, current_user.workshop_id, db)
    rows = get_vehicle_life_rows(vehicle_id, current_user.workshop_id, db)

    total_invested = sum(Decimal(str(row.get("subtotal") or 0)) for row in rows)
    last_km = rows[0].get("current_km") if rows else None

    groups = {}
    order_sequence = []
    for row in rows:
        order_id = row["work_order_id"]
        if order_id not in groups:
            groups[order_id] = []
            order_sequence.append(order_id)
        groups[order_id].append(row)

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.35 * cm,
        leftMargin=1.35 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.5 * cm,
        title=f"Vida del Auto - {safe(header.get('plate'))}",
        author=safe(header.get("workshop_name"), "SIADAUTO"),
    )

    styles = getSampleStyleSheet()

    blue = colors.HexColor("#164E9E")
    dark_blue = colors.HexColor("#0B1736")
    light_blue = colors.HexColor("#EAF3FF")
    silver = colors.HexColor("#E5E7EB")
    slate = colors.HexColor("#475569")
    green = colors.HexColor("#0F8A5F")

    styles.add(
        ParagraphStyle(
            name="Brand",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=blue,
            leading=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=27,
            textColor=dark_blue,
            alignment=TA_LEFT,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Subtitle",
            parent=styles["Normal"],
            fontSize=10.5,
            leading=14,
            textColor=slate,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=17,
            textColor=dark_blue,
            spaceBefore=4,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CardLabel",
            parent=styles["Normal"],
            fontSize=8.5,
            textColor=slate,
            leading=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CardValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=dark_blue,
            leading=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=slate,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Footer",
            parent=styles["Normal"],
            fontSize=7.5,
            textColor=slate,
            alignment=TA_CENTER,
        )
    )

    def page_footer(canvas, doc_obj):
        canvas.saveState()
        width, _ = A4

        canvas.setStrokeColor(silver)
        canvas.setLineWidth(0.5)
        canvas.line(1.35 * cm, 1.05 * cm, width - 1.35 * cm, 1.05 * cm)

        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(slate)
        workshop_footer = safe(
            header.get("workshop_footer_text"),
            f"Generado por {safe(header.get('workshop_name'), 'SIADAUTO')}",
        )
        footer_text = (
            f"{workshop_footer} - {datetime.now().strftime('%d/%m/%Y %H:%M')} "
            f"- Página {doc_obj.page}"
        )
        canvas.drawCentredString(width / 2, 0.68 * cm, footer_text)
        canvas.restoreState()

    story = []

    workshop_name = safe(header.get("workshop_name"), "Taller")
    workshop_business_name = header.get("workshop_business_name")
    workshop_ruc = header.get("workshop_ruc")
    workshop_phone = header.get("workshop_phone")
    workshop_email = header.get("workshop_email")
    workshop_address = header.get("workshop_address")
    workshop_logo = load_remote_logo(header.get("workshop_logo_url"))

    workshop_lines = [f"<b>{paragraph_text(workshop_name)}</b>"]
    if workshop_business_name and workshop_business_name != workshop_name:
        workshop_lines.append(paragraph_text(workshop_business_name))
    if workshop_ruc:
        workshop_lines.append(f"RUC: {paragraph_text(workshop_ruc)}")

    contact_parts = [
        paragraph_text(value)
        for value in (workshop_phone, workshop_email)
        if value
    ]
    if contact_parts:
        workshop_lines.append(" · ".join(contact_parts))
    if workshop_address:
        workshop_lines.append(paragraph_text(workshop_address))

    identity_block = Paragraph(
        "<br/>".join(workshop_lines),
        ParagraphStyle(
            "WorkshopIdentity",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=dark_blue,
        ),
    )

    top = Table(
        [
            [
                workshop_logo or "",
                identity_block,
            ],
            [
                "",
                [
                    Paragraph("Vida del Auto", styles["ReportTitle"]),
                    Paragraph(
                        "Historial inteligente de mantenimiento, reparaciones y próximos cuidados.",
                        styles["Subtitle"],
                    ),
                ],
            ],
        ],
        colWidths=[4.5 * cm, 13.0 * cm],
    )
    top.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("SPAN", (0, 0), (0, 1)),
                ("BOX", (0, 0), (-1, -1), 0.8, blue),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(top)
    story.append(Spacer(1, 0.35 * cm))

    vehicle_name = " ".join(
        part for part in [safe(header.get("brand"), ""), safe(header.get("model"), "")]
        if part
    ).strip() or "Vehículo"

    cards = [
        [
            Paragraph("VEHÍCULO", styles["CardLabel"]),
            Paragraph("CLIENTE", styles["CardLabel"]),
            Paragraph("ÚLTIMO KM", styles["CardLabel"]),
            Paragraph("TOTAL INVERTIDO", styles["CardLabel"]),
        ],
        [
            Paragraph(
                f"{vehicle_name}<br/><font size='9'>{safe(header.get('plate'), 'Sin placa')}</font>",
                styles["CardValue"],
            ),
            Paragraph(
                f"{safe(header.get('client_name'), 'Sin cliente')}<br/>"
                f"<font size='9'>{safe(header.get('client_phone'), '')}</font>",
                styles["CardValue"],
            ),
            Paragraph(km_text(last_km), styles["CardValue"]),
            Paragraph(money(total_invested), styles["CardValue"]),
        ],
    ]

    card_table = Table(cards, colWidths=[4.4 * cm, 4.4 * cm, 4.2 * cm, 4.5 * cm])
    card_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.6, silver),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, silver),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("TOPPADDING", (0, 1), (-1, 1), 2),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(card_table)
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Historial del vehículo", styles["SectionTitle"]))

    if not rows:
        story.append(
            Paragraph("Este vehículo todavía no tiene historial registrado.", styles["Small"])
        )
    else:
        for index, order_id in enumerate(order_sequence):
            items = groups[order_id]
            first = items[0]
            order_total = sum(
                Decimal(str(item.get("subtotal") or 0))
                for item in items
            )

            order_header = Table(
                [
                    [
                        Paragraph(
                            "<b>Mantenimiento realizado</b><br/>"
                            f"<font size='11'><b>{long_date_es(first.get('work_order_date'))}</b></font><br/>"
                            f"<font size='8'>OT #{safe(first.get('order_number'), order_id)}</font>",
                            styles["CardValue"],
                        ),
                        Paragraph(
                            f"<b>{km_text(first.get('current_km'))}</b>",
                            ParagraphStyle(
                                "OrderKm",
                                parent=styles["CardValue"],
                                alignment=TA_CENTER,
                            ),
                        ),
                        Paragraph(
                            f"<b>{money(order_total)}</b><br/><font size='8'>Total OT</font>",
                            ParagraphStyle(
                                "OrderTotal",
                                parent=styles["CardValue"],
                                alignment=TA_RIGHT,
                                textColor=green,
                            ),
                        ),
                    ]
                ],
                colWidths=[8.3 * cm, 4.3 * cm, 4.9 * cm],
            )
            order_header.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                        ("BOX", (0, 0), (-1, -1), 0.6, silver),
                        ("LEFTPADDING", (0, 0), (-1, -1), 9),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )

            item_rows = [["Tipo", "Descripción", "Cant.", "V. unitario", "Subtotal", "Próximo cuidado"]]
            for item in items:
                next_text_parts = []
                if item.get("next_service_km"):
                    next_text_parts.append(km_text(item.get("next_service_km")))
                if item.get("next_service_date"):
                    next_text_parts.append(str(item.get("next_service_date")))

                item_rows.append(
                    [
                        service_type_label(item.get("item_type")),
                        Paragraph(safe(item.get("description")), styles["Small"]),
                        safe(item.get("quantity"), "0"),
                        money(item.get("unit_price")),
                        money(item.get("subtotal")),
                        " / ".join(next_text_parts) if next_text_parts else "-",
                    ]
                )

            item_table = Table(
                item_rows,
                colWidths=[2.4 * cm, 5.3 * cm, 1.5 * cm, 2.5 * cm, 2.5 * cm, 3.3 * cm],
                repeatRows=1,
            )
            item_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), dark_blue),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 8),
                        ("GRID", (0, 0), (-1, -1), 0.45, silver),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (2, 1), (4, -1), "RIGHT"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ]
                )
            )

            story.append(KeepTogether([order_header, Spacer(1, 0.12 * cm), item_table]))
            if index < len(order_sequence) - 1:
                story.append(Spacer(1, 0.35 * cm))

    story.append(Spacer(1, 0.65 * cm))

    notice = Table(
        [[Paragraph(
            "<b>Importante:</b> Los próximos servicios son estimados según el kilometraje "
            "y las fechas registradas por el taller. El estado real del vehículo debe "
            "confirmarse mediante una inspección técnica.",
            styles["Small"],
        )]],
        colWidths=[17.5 * cm],
    )
    notice.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7ED")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#FDBA74")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(notice)

    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    buffer.seek(0)

    plate = safe(header.get("plate"), str(vehicle_id)).replace(" ", "_")
    filename = f"vida_del_auto_{plate}.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


@router.get("/reminders/pending")
def get_pending_vehicle_life_reminders(
    days_ahead: int = Query(default=15, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    limit_date = today + timedelta(days=days_ahead)

    query = text("""
        SELECT
            wo.id AS work_order_id,
            wo.vehicle_id,
            wo.current_km,
            wo.entry_date AS work_order_date,

            v.plate,
            v.brand,
            v.model,

            c.full_name AS client_name,
            c.phone AS client_phone,

            woi.id AS item_id,
            woi.item_type,
            woi.description,
            woi.next_service_km,
            woi.next_service_date,
            woi.reminder_enabled,
            woi.reminder_sent

        FROM work_order_items woi
        INNER JOIN work_orders wo
            ON wo.id = woi.work_order_id
        LEFT JOIN vehicles v
            ON v.id = wo.vehicle_id
        LEFT JOIN clients c
            ON c.id = wo.client_id
        WHERE wo.workshop_id = :workshop_id
          AND woi.reminder_enabled = TRUE
          AND woi.reminder_sent = FALSE
          AND woi.next_service_date IS NOT NULL
          AND woi.next_service_date BETWEEN :today AND :limit_date
        ORDER BY woi.next_service_date ASC
    """)

    rows = [
        row_to_dict(row)
        for row in db.execute(
            query,
            {
                "workshop_id": current_user.workshop_id,
                "today": today,
                "limit_date": limit_date,
            },
        ).fetchall()
    ]

    reminders = []

    for row in rows:
        vehicle_name = " ".join(
            str(x) for x in [row.get("brand"), row.get("model")] if x
        ).strip()

        next_km = row.get("next_service_km")
        next_date = row.get("next_service_date")

        message = (
            f"Hola 👋, te saluda GARAGE SIADAUTO.\n\n"
            f"Tu {vehicle_name or 'vehículo'}"
            f"{' placa ' + row.get('plate') if row.get('plate') else ''} "
            f"está próximo a: {row.get('description')}.\n\n"
            f"Según nuestro historial, corresponde aproximadamente "
            f"{'a los ' + str(next_km) + ' km' if next_km else ''}"
            f"{' o ' if next_km and next_date else ''}"
            f"{'para el ' + str(next_date) if next_date else ''}.\n\n"
            f"¿Deseas agendar una revisión?"
        )

        reminders.append({
            "work_order_id": row.get("work_order_id"),
            "item_id": row.get("item_id"),
            "vehicle_id": row.get("vehicle_id"),
            "client_name": row.get("client_name"),
            "client_phone": row.get("client_phone"),
            "plate": row.get("plate"),
            "description": row.get("description"),
            "next_service_km": next_km,
            "next_service_date": next_date,
            "whatsapp_message": message,
        })

    return reminders
