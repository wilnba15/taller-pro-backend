import base64
import hashlib
import os
import secrets
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree

DS_NS = "http://www.w3.org/2000/09/xmldsig#"
XADES_NS = "http://uri.etsi.org/01903/v1.3.2#"
SIGNED_PROPERTIES_TYPE = "http://uri.etsi.org/01903#SignedProperties"
C14N_ALGORITHM = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
RSA_SHA1_ALGORITHM = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
SHA1_ALGORITHM = "http://www.w3.org/2000/09/xmldsig#sha1"
ENVELOPED_ALGORITHM = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"

def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")

def _sha1_b64(data: bytes) -> str:
    return _b64(hashlib.sha1(data).digest())

def _c14n(node) -> bytes:
    return etree.tostring(node, method="c14n", exclusive=False, with_comments=False)

def _int_b64(value: int) -> str:
    raw = b"\x00" if value == 0 else value.to_bytes((value.bit_length() + 7) // 8, "big")
    return _b64(raw)

def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def load_pkcs12_certificate(p12_path: str | None = None, p12_password: str | None = None):
    path = (
        p12_path
        or os.getenv("SRI_P12_BASE64_PATH")
        or os.getenv("SRI_P12_PATH")
        or "/etc/secrets/siadauto_firma.p12.base64"
    )
    password = p12_password or os.getenv("SRI_P12_PASSWORD")

    if password is None:
        raise ValueError("Falta SRI_P12_PASSWORD en las variables de entorno")
    if not os.path.exists(path):
        raise ValueError(f"No existe el archivo de firma en la ruta configurada: {path}")

    with open(path, "rb") as certificate_file:
        raw_content = certificate_file.read()

    if not raw_content:
        raise ValueError("El archivo de firma está vacío")

    if path.lower().endswith((".base64", ".b64", ".txt")):
        try:
            compact_base64 = b"".join(raw_content.split())
            p12_bytes = base64.b64decode(compact_base64, validate=True)
        except Exception as exc:
            raise ValueError(
                "El Secret File de la firma no contiene un Base64 válido"
            ) from exc
    else:
        p12_bytes = raw_content

    try:
        private_key, certificate, chain = pkcs12.load_key_and_certificates(
            p12_bytes,
            password.encode("utf-8"),
        )
    except Exception as exc:
        raise ValueError(
            "No se pudo abrir el certificado .p12. Verifique el archivo y la contraseña."
        ) from exc

    if private_key is None or certificate is None:
        raise ValueError("El .p12 no contiene llave privada y certificado válidos")
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise ValueError("El certificado debe utilizar una llave privada RSA")
    if private_key.key_size < 2048:
        raise ValueError("La llave RSA debe tener al menos 2048 bits")

    now = datetime.now(timezone.utc)
    not_before = getattr(certificate, "not_valid_before_utc", certificate.not_valid_before.replace(tzinfo=timezone.utc))
    not_after = getattr(certificate, "not_valid_after_utc", certificate.not_valid_after.replace(tzinfo=timezone.utc))

    if now < _aware(not_before):
        raise ValueError("El certificado todavía no es válido")
    if now > _aware(not_after):
        raise ValueError("El certificado de firma electrónica está vencido")

    return private_key, certificate, chain or []

def certificate_metadata(certificate: x509.Certificate) -> dict:
    not_before = getattr(certificate, "not_valid_before_utc", certificate.not_valid_before.replace(tzinfo=timezone.utc))
    not_after = getattr(certificate, "not_valid_after_utc", certificate.not_valid_after.replace(tzinfo=timezone.utc))
    return {
        "subject": certificate.subject.rfc4514_string(),
        "issuer": certificate.issuer.rfc4514_string(),
        "serial": str(certificate.serial_number),
        "valid_from": _aware(not_before),
        "valid_to": _aware(not_after),
    }

def sign_xml_xades_bes(xml_content: str, *, p12_path: str | None = None, p12_password: str | None = None):
    private_key, certificate, _ = load_pkcs12_certificate(p12_path, p12_password)

    parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False, no_network=True)
    try:
        root = etree.fromstring(xml_content.encode("utf-8"), parser=parser)
    except Exception as exc:
        raise ValueError("El XML no es válido y no puede ser firmado") from exc

    if root.get("id") != "comprobante":
        raise ValueError('El nodo raíz debe tener id="comprobante"')

    if root.xpath("./ds:Signature", namespaces={"ds": DS_NS}):
        raise ValueError("El XML ya contiene una firma electrónica")

    token = str(secrets.randbelow(900000) + 100000)
    signature_id = f"Signature{token}"
    signed_properties_id = f"{signature_id}-SignedProperties{secrets.randbelow(90000)+10000}"
    key_info_id = f"Certificate{secrets.randbelow(9000000)+1000000}"
    signature_value_id = f"SignatureValue{secrets.randbelow(900000)+100000}"
    reference_id = f"Reference-ID-{secrets.randbelow(900000)+100000}"
    signed_properties_reference_id = f"SignedPropertiesID{secrets.randbelow(900000)+100000}"
    object_id = f"{signature_id}-Object{secrets.randbelow(900000)+100000}"

    signature = etree.Element(etree.QName(DS_NS, "Signature"), nsmap={"ds": DS_NS, "etsi": XADES_NS})
    signature.set("Id", signature_id)

    signed_info = etree.SubElement(signature, etree.QName(DS_NS, "SignedInfo"))
    cm = etree.SubElement(signed_info, etree.QName(DS_NS, "CanonicalizationMethod"))
    cm.set("Algorithm", C14N_ALGORITHM)
    sm = etree.SubElement(signed_info, etree.QName(DS_NS, "SignatureMethod"))
    sm.set("Algorithm", RSA_SHA1_ALGORITHM)

    signature_value = etree.SubElement(signature, etree.QName(DS_NS, "SignatureValue"))
    signature_value.set("Id", signature_value_id)

    key_info = etree.SubElement(signature, etree.QName(DS_NS, "KeyInfo"))
    key_info.set("Id", key_info_id)
    x509_data = etree.SubElement(key_info, etree.QName(DS_NS, "X509Data"))
    x509_cert = etree.SubElement(x509_data, etree.QName(DS_NS, "X509Certificate"))
    cert_der = certificate.public_bytes(serialization.Encoding.DER)
    x509_cert.text = _b64(cert_der)

    key_value = etree.SubElement(key_info, etree.QName(DS_NS, "KeyValue"))
    rsa_key_value = etree.SubElement(key_value, etree.QName(DS_NS, "RSAKeyValue"))
    pub = certificate.public_key().public_numbers()
    modulus = etree.SubElement(rsa_key_value, etree.QName(DS_NS, "Modulus"))
    modulus.text = _int_b64(pub.n)
    exponent = etree.SubElement(rsa_key_value, etree.QName(DS_NS, "Exponent"))
    exponent.text = _int_b64(pub.e)

    obj = etree.SubElement(signature, etree.QName(DS_NS, "Object"))
    obj.set("Id", object_id)
    qp = etree.SubElement(obj, etree.QName(XADES_NS, "QualifyingProperties"))
    qp.set("Target", f"#{signature_id}")
    sp = etree.SubElement(qp, etree.QName(XADES_NS, "SignedProperties"))
    sp.set("Id", signed_properties_id)
    ssp = etree.SubElement(sp, etree.QName(XADES_NS, "SignedSignatureProperties"))

    signing_time = etree.SubElement(ssp, etree.QName(XADES_NS, "SigningTime"))
    signing_time.text = datetime.now(ZoneInfo("America/Guayaquil")).isoformat(timespec="seconds")

    signing_cert = etree.SubElement(ssp, etree.QName(XADES_NS, "SigningCertificate"))
    cert_node = etree.SubElement(signing_cert, etree.QName(XADES_NS, "Cert"))
    cert_digest = etree.SubElement(cert_node, etree.QName(XADES_NS, "CertDigest"))
    dm = etree.SubElement(cert_digest, etree.QName(DS_NS, "DigestMethod"))
    dm.set("Algorithm", SHA1_ALGORITHM)
    dv = etree.SubElement(cert_digest, etree.QName(DS_NS, "DigestValue"))
    dv.text = _sha1_b64(cert_der)

    issuer_serial = etree.SubElement(cert_node, etree.QName(XADES_NS, "IssuerSerial"))
    issuer = etree.SubElement(issuer_serial, etree.QName(DS_NS, "X509IssuerName"))
    issuer.text = certificate.issuer.rfc4514_string()
    serial = etree.SubElement(issuer_serial, etree.QName(DS_NS, "X509SerialNumber"))
    serial.text = str(certificate.serial_number)

    sdop = etree.SubElement(sp, etree.QName(XADES_NS, "SignedDataObjectProperties"))
    dof = etree.SubElement(sdop, etree.QName(XADES_NS, "DataObjectFormat"))
    dof.set("ObjectReference", f"#{reference_id}")
    desc = etree.SubElement(dof, etree.QName(XADES_NS, "Description"))
    desc.text = "contenido comprobante"
    mime = etree.SubElement(dof, etree.QName(XADES_NS, "MimeType"))
    mime.text = "text/xml"

    comprobante_digest = _sha1_b64(_c14n(root))
    signed_properties_digest = _sha1_b64(_c14n(sp))
    key_info_digest = _sha1_b64(_c14n(key_info))

    ref_sp = etree.SubElement(signed_info, etree.QName(DS_NS, "Reference"))
    ref_sp.set("Id", signed_properties_reference_id)
    ref_sp.set("Type", SIGNED_PROPERTIES_TYPE)
    ref_sp.set("URI", f"#{signed_properties_id}")
    dm = etree.SubElement(ref_sp, etree.QName(DS_NS, "DigestMethod")); dm.set("Algorithm", SHA1_ALGORITHM)
    dv = etree.SubElement(ref_sp, etree.QName(DS_NS, "DigestValue")); dv.text = signed_properties_digest

    ref_ki = etree.SubElement(signed_info, etree.QName(DS_NS, "Reference"))
    ref_ki.set("URI", f"#{key_info_id}")
    dm = etree.SubElement(ref_ki, etree.QName(DS_NS, "DigestMethod")); dm.set("Algorithm", SHA1_ALGORITHM)
    dv = etree.SubElement(ref_ki, etree.QName(DS_NS, "DigestValue")); dv.text = key_info_digest

    ref_doc = etree.SubElement(signed_info, etree.QName(DS_NS, "Reference"))
    ref_doc.set("Id", reference_id)
    ref_doc.set("URI", "#comprobante")
    transforms = etree.SubElement(ref_doc, etree.QName(DS_NS, "Transforms"))
    tr = etree.SubElement(transforms, etree.QName(DS_NS, "Transform")); tr.set("Algorithm", ENVELOPED_ALGORITHM)
    dm = etree.SubElement(ref_doc, etree.QName(DS_NS, "DigestMethod")); dm.set("Algorithm", SHA1_ALGORITHM)
    dv = etree.SubElement(ref_doc, etree.QName(DS_NS, "DigestValue")); dv.text = comprobante_digest

    signed_info_bytes = _c14n(signed_info)
    signature_bytes = private_key.sign(signed_info_bytes, padding.PKCS1v15(), hashes.SHA1())
    signature_value.text = _b64(signature_bytes)

    root.append(signature)

    signed_xml = etree.tostring(
        root,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=False,
    ).decode("utf-8")

    metadata = certificate_metadata(certificate)
    metadata.update({
        "signature_algorithm": "RSA-SHA1",
        "key_size": private_key.key_size,
        "xades_version": "1.3.2",
        "signature_type": "ENVELOPED",
    })
    return signed_xml, metadata
