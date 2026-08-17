import base64
from dataclasses import dataclass
from typing import Any

import httpx
from lxml import etree


SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
RECEPTION_NS = "http://ec.gob.sri.ws.recepcion"
AUTHORIZATION_NS = "http://ec.gob.sri.ws.autorizacion"

TEST_RECEPTION_URL = (
    "https://celcer.sri.gob.ec/"
    "comprobantes-electronicos-ws/"
    "RecepcionComprobantesOffline"
)

TEST_AUTHORIZATION_URL = (
    "https://celcer.sri.gob.ec/"
    "comprobantes-electronicos-ws/"
    "AutorizacionComprobantesOffline"
)

PROD_RECEPTION_URL = (
    "https://cel.sri.gob.ec/"
    "comprobantes-electronicos-ws/"
    "RecepcionComprobantesOffline"
)

PROD_AUTHORIZATION_URL = (
    "https://cel.sri.gob.ec/"
    "comprobantes-electronicos-ws/"
    "AutorizacionComprobantesOffline"
)


@dataclass
class SriEndpoints:
    reception: str
    authorization: str


def endpoints_for_environment(environment: str) -> SriEndpoints:
    normalized = (environment or "pruebas").strip().lower()

    if normalized in {
        "pruebas",
        "prueba",
        "test",
        "certificacion",
        "certificación",
        "1",
    }:
        return SriEndpoints(
            reception=TEST_RECEPTION_URL,
            authorization=TEST_AUTHORIZATION_URL,
        )

    if normalized in {
        "produccion",
        "producción",
        "production",
        "2",
    }:
        return SriEndpoints(
            reception=PROD_RECEPTION_URL,
            authorization=PROD_AUTHORIZATION_URL,
        )

    raise ValueError(
        "Ambiente SRI no válido"
    )


def _text(node, xpath: str) -> str | None:
    result = node.xpath(xpath)
    if not result:
        return None

    value = result[0]

    if isinstance(value, etree._Element):
        return value.text

    return str(value)


def _messages_from(node) -> list[dict[str, Any]]:
    messages = []

    for message in node.xpath(
        ".//*[local-name()='mensaje']"
    ):
        messages.append(
            {
                "identificador": _text(
                    message,
                    "./*[local-name()='identificador']/text()",
                ),
                "mensaje": _text(
                    message,
                    "./*[local-name()='mensaje']/text()",
                ),
                "informacion_adicional": _text(
                    message,
                    "./*[local-name()='informacionAdicional']/text()",
                ),
                "tipo": _text(
                    message,
                    "./*[local-name()='tipo']/text()",
                ),
            }
        )

    return messages


def _parse_soap(xml_bytes: bytes) -> etree._Element:
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        recover=False,
    )

    try:
        return etree.fromstring(
            xml_bytes,
            parser=parser,
        )
    except Exception as exc:
        raise ValueError(
            "El SRI devolvió una respuesta XML/SOAP inválida"
        ) from exc


def build_reception_envelope(
    signed_xml: str,
) -> bytes:
    envelope = etree.Element(
        etree.QName(SOAP_NS, "Envelope"),
        nsmap={
            "soapenv": SOAP_NS,
            "rec": RECEPTION_NS,
        },
    )

    body = etree.SubElement(
        envelope,
        etree.QName(SOAP_NS, "Body"),
    )

    operation = etree.SubElement(
        body,
        etree.QName(
            RECEPTION_NS,
            "validarComprobante",
        ),
    )

    xml_node = etree.SubElement(
        operation,
        "xml",
    )

    xml_node.text = base64.b64encode(
        signed_xml.encode("utf-8")
    ).decode("ascii")

    return etree.tostring(
        envelope,
        encoding="UTF-8",
        xml_declaration=True,
    )


def build_authorization_envelope(
    access_key: str,
) -> bytes:
    envelope = etree.Element(
        etree.QName(SOAP_NS, "Envelope"),
        nsmap={
            "soapenv": SOAP_NS,
            "aut": AUTHORIZATION_NS,
        },
    )

    body = etree.SubElement(
        envelope,
        etree.QName(SOAP_NS, "Body"),
    )

    operation = etree.SubElement(
        body,
        etree.QName(
            AUTHORIZATION_NS,
            "autorizacionComprobante",
        ),
    )

    key_node = etree.SubElement(
        operation,
        "claveAccesoComprobante",
    )

    key_node.text = access_key

    return etree.tostring(
        envelope,
        encoding="UTF-8",
        xml_declaration=True,
    )


def send_to_reception(
    *,
    signed_xml: str,
    environment: str,
    timeout_seconds: float = 35.0,
) -> dict:
    endpoints = endpoints_for_environment(
        environment
    )

    payload = build_reception_envelope(
        signed_xml
    )

    try:
        with httpx.Client(
            timeout=timeout_seconds,
            verify=True,
            follow_redirects=True,
        ) as client:
            response = client.post(
                endpoints.reception,
                content=payload,
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": '""',
                },
            )

    except httpx.HTTPError as exc:
        raise ValueError(
            f"No se pudo conectar con el WS de recepción del SRI: {exc}"
        ) from exc

    if response.status_code >= 400:
        raise ValueError(
            "El WS de recepción del SRI respondió "
            f"HTTP {response.status_code}"
        )

    root = _parse_soap(
        response.content
    )

    soap_fault = root.xpath(
        "//*[local-name()='Fault']"
    )

    if soap_fault:
        fault_text = _text(
            soap_fault[0],
            ".//*[local-name()='faultstring']/text()",
        )
        raise ValueError(
            f"SOAP Fault SRI recepción: {fault_text or 'sin detalle'}"
        )

    response_node = root.xpath(
        "//*[local-name()='RespuestaRecepcionComprobante']"
    )

    if not response_node:
        raise ValueError(
            "La respuesta del SRI no contiene "
            "RespuestaRecepcionComprobante"
        )

    node = response_node[0]

    state = _text(
        node,
        "./*[local-name()='estado']/text()",
    )

    return {
        "estado": state,
        "mensajes": _messages_from(node),
        "raw": response.text,
    }


def query_authorization(
    *,
    access_key: str,
    environment: str,
    timeout_seconds: float = 35.0,
) -> dict:
    endpoints = endpoints_for_environment(
        environment
    )

    payload = build_authorization_envelope(
        access_key
    )

    try:
        with httpx.Client(
            timeout=timeout_seconds,
            verify=True,
            follow_redirects=True,
        ) as client:
            response = client.post(
                endpoints.authorization,
                content=payload,
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": '""',
                },
            )

    except httpx.HTTPError as exc:
        raise ValueError(
            f"No se pudo conectar con el WS de autorización del SRI: {exc}"
        ) from exc

    if response.status_code >= 400:
        raise ValueError(
            "El WS de autorización del SRI respondió "
            f"HTTP {response.status_code}"
        )

    root = _parse_soap(
        response.content
    )

    soap_fault = root.xpath(
        "//*[local-name()='Fault']"
    )

    if soap_fault:
        fault_text = _text(
            soap_fault[0],
            ".//*[local-name()='faultstring']/text()",
        )
        raise ValueError(
            f"SOAP Fault SRI autorización: {fault_text or 'sin detalle'}"
        )

    response_nodes = root.xpath(
        "//*[local-name()='RespuestaAutorizacionComprobante']"
    )

    if not response_nodes:
        raise ValueError(
            "La respuesta del SRI no contiene "
            "RespuestaAutorizacionComprobante"
        )

    response_node = response_nodes[0]

    number_of_documents = _text(
        response_node,
        "./*[local-name()='numeroComprobantes']/text()",
    )

    authorization_nodes = response_node.xpath(
        ".//*[local-name()='autorizacion']"
    )

    if not authorization_nodes:
        return {
            "numero_comprobantes": number_of_documents,
            "estado": "PPR",
            "numero_autorizacion": None,
            "fecha_autorizacion": None,
            "ambiente": None,
            "comprobante": None,
            "mensajes": [],
            "raw": response.text,
        }

    authorization = authorization_nodes[-1]

    state = _text(
        authorization,
        "./*[local-name()='estado']/text()",
    )

    authorization_number = _text(
        authorization,
        "./*[local-name()='numeroAutorizacion']/text()",
    )

    authorization_date = _text(
        authorization,
        "./*[local-name()='fechaAutorizacion']/text()",
    )

    authorization_environment = _text(
        authorization,
        "./*[local-name()='ambiente']/text()",
    )

    authorized_document = _text(
        authorization,
        "./*[local-name()='comprobante']/text()",
    )

    return {
        "numero_comprobantes": number_of_documents,
        "estado": state,
        "numero_autorizacion": authorization_number,
        "fecha_autorizacion": authorization_date,
        "ambiente": authorization_environment,
        "comprobante": authorized_document,
        "mensajes": _messages_from(authorization),
        "raw": response.text,
    }
