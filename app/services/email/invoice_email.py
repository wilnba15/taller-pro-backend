import base64
import html
import os
import re

import resend


DEFAULT_FROM_EMAIL = "facturacion@facturas.siadauto.com"


def _safe_display_name(value: str | None, fallback: str = "SIADAUTO") -> str:
    """
    Limpia el nombre visible del remitente para evitar saltos de línea
    o caracteres que puedan romper el encabezado From.
    """
    value = (value or fallback).strip()
    value = re.sub(r"[\r\n<>]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or fallback


def _money(value) -> str:
    try:
        return f"${float(value or 0):,.2f}"
    except Exception:
        return "$0.00"


def _response_id(response) -> str | None:
    if isinstance(response, dict):
        return response.get("id")

    return getattr(response, "id", None)


def send_authorized_invoice_email(
    *,
    invoice,
    workshop,
    submission,
    ride_pdf: bytes,
) -> dict:
    """
    Envía por Resend una factura electrónica AUTORIZADA.

    Adjuntos:
    - RIDE / PDF
    - XML autorizado

    La factura debe haber sido autorizada previamente por el SRI.
    """

    api_key = os.getenv("RESEND_API_KEY")

    if not api_key:
        raise ValueError(
            "Falta RESEND_API_KEY en las variables de entorno"
        )

    recipient = (invoice.client_email or "").strip()

    if not recipient:
        raise ValueError(
            "La factura no tiene correo electrónico del cliente"
        )

    authorization_status = (
        submission.authorization_status
        or ""
    ).strip().upper()

    if authorization_status not in {
        "AUTORIZADO",
        "AUT",
    }:
        raise ValueError(
            "Solo se puede enviar por correo una factura autorizada por el SRI"
        )

    authorized_xml = submission.authorized_xml

    if not authorized_xml:
        raise ValueError(
            "El SRI no devolvió el XML autorizado de esta factura"
        )

    if not ride_pdf:
        raise ValueError(
            "No se pudo generar el RIDE de la factura"
        )

    workshop_name = (
        workshop.name
        or workshop.business_name
        or "Taller"
    )

    sender_name = _safe_display_name(workshop_name)
    from_email = (
        os.getenv("RESEND_FROM_EMAIL")
        or DEFAULT_FROM_EMAIL
    ).strip()

    reply_to = (workshop.email or "").strip() or None

    invoice_number = str(invoice.invoice_number)
    total = _money(invoice.total)

    client_name = html.escape(
        str(invoice.client_name or "Cliente")
    )
    workshop_name_html = html.escape(
        str(workshop_name)
    )
    invoice_number_html = html.escape(
        invoice_number
    )
    total_html = html.escape(
        total
    )

    authorization_number_html = html.escape(
        str(
            submission.authorization_number
            or submission.access_key
            or "-"
        )
    )

    subject = (
        f"Factura electrónica {invoice_number} - "
        f"{workshop_name}"
    )

    html_body = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:auto;color:#1f2937;">
      <div style="padding:24px;border:1px solid #e5e7eb;border-radius:14px;">
        <h2 style="margin-top:0;color:#0f172a;">
          Factura electrónica
        </h2>

        <p>Estimado/a <strong>{client_name}</strong>:</p>

        <p>
          Adjuntamos su factura electrónica emitida por
          <strong>{workshop_name_html}</strong>.
        </p>

        <div style="background:#f8fafc;padding:16px;border-radius:10px;margin:20px 0;">
          <p style="margin:0 0 8px 0;">
            <strong>Factura:</strong> {invoice_number_html}
          </p>
          <p style="margin:0 0 8px 0;">
            <strong>Total:</strong> {total_html}
          </p>
          <p style="margin:0;">
            <strong>Autorización SRI:</strong>
            {authorization_number_html}
          </p>
        </div>

        <p>
          En este correo encontrará adjuntos:
        </p>

        <ul>
          <li>RIDE de la factura en formato PDF.</li>
          <li>Comprobante electrónico autorizado en formato XML.</li>
        </ul>

        <p style="margin-bottom:0;">
          Gracias por su confianza.
        </p>

        <p style="margin-top:6px;">
          <strong>{workshop_name_html}</strong>
        </p>
      </div>

      <p style="font-size:12px;color:#64748b;text-align:center;margin-top:14px;">
        Enviado automáticamente mediante SIADAUTO.
      </p>
    </div>
    """

    text_body = (
        f"Estimado/a {invoice.client_name or 'Cliente'},\n\n"
        f"Adjuntamos su factura electrónica emitida por {workshop_name}.\n"
        f"Factura: {invoice_number}\n"
        f"Total: {total}\n"
        f"Autorización SRI: "
        f"{submission.authorization_number or submission.access_key or '-'}\n\n"
        "Adjuntos: RIDE en PDF y XML autorizado.\n\n"
        f"Gracias por su confianza.\n{workshop_name}"
    )

    pdf_filename = (
        f"RIDE_factura_{invoice_number}.pdf"
    )

    xml_filename = (
        f"factura_autorizada_{invoice_number}.xml"
    )

    resend.api_key = api_key

    params = {
        "from": f"{sender_name} <{from_email}>",
        "to": [recipient],
        "subject": subject,
        "html": html_body,
        "text": text_body,
        "attachments": [
            {
                "filename": pdf_filename,
                "content": base64.b64encode(
                    ride_pdf
                ).decode("ascii"),
            },
            {
                "filename": xml_filename,
                "content": base64.b64encode(
                    authorized_xml.encode("utf-8")
                ).decode("ascii"),
            },
        ],
    }

    if reply_to:
        params["reply_to"] = reply_to

    try:
        response = resend.Emails.send(params)
    except Exception as exc:
        raise ValueError(
            f"No se pudo enviar la factura por correo: {exc}"
        ) from exc

    return {
        "sent": True,
        "provider": "resend",
        "provider_id": _response_id(response),
        "to": recipient,
        "from": f"{sender_name} <{from_email}>",
        "reply_to": reply_to,
        "subject": subject,
    }
