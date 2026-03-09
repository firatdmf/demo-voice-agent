"""Validators for TCKN, phone numbers, and dates."""
import re
from datetime import date, datetime
from typing import Optional, Tuple


def validate_tckn(tckn: str) -> Tuple[bool, str]:
    """Validate Turkish ID number (TCKN) with checksum algorithm.
    Returns (is_valid, error_message)."""
    tckn = tckn.strip().replace(" ", "")

    if not tckn.isdigit():
        return False, "TCKN sadece rakamlardan olusmalidir."

    if len(tckn) != 11:
        return False, "TCKN 11 haneli olmalidir."

    if tckn[0] == "0":
        return False, "TCKN sifir ile baslayamaz."

    digits = [int(d) for d in tckn]

    # 10th digit check: ((d1+d3+d5+d7+d9)*7 - (d2+d4+d6+d8)) % 10 == d10
    odd_sum = sum(digits[i] for i in range(0, 9, 2))  # 1st,3rd,5th,7th,9th
    even_sum = sum(digits[i] for i in range(1, 8, 2))  # 2nd,4th,6th,8th
    check_10 = (odd_sum * 7 - even_sum) % 10
    if check_10 != digits[9]:
        return False, "TCKN checksum hatali (10. hane)."

    # 11th digit check: sum of first 10 digits % 10 == d11
    check_11 = sum(digits[:10]) % 10
    if check_11 != digits[10]:
        return False, "TCKN checksum hatali (11. hane)."

    return True, ""


def normalize_phone(phone: str) -> Tuple[Optional[str], str]:
    """Normalize Turkish phone number to +90XXXXXXXXXX format.
    Returns (normalized_phone, error_message)."""
    phone = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    # Remove leading +
    if phone.startswith("+"):
        phone = phone[1:]

    # Remove leading 00 (international)
    if phone.startswith("00"):
        phone = phone[2:]

    # Handle 90XXXXXXXXXX
    if phone.startswith("90") and len(phone) == 12:
        phone = phone[2:]

    # Handle 0XXXXXXXXXX
    if phone.startswith("0") and len(phone) == 11:
        phone = phone[1:]

    # Now should be 10 digits starting with 5
    if not phone.isdigit():
        return None, "Telefon numarasi sadece rakam icermelidir."

    if len(phone) != 10:
        return None, "Telefon numarasi 10 haneli olmalidir (5XX XXX XX XX)."

    if not phone.startswith("5"):
        return None, "GSM numarasi 5 ile baslamalidir."

    return f"+90{phone}", ""


def parse_date(date_str: str) -> Tuple[Optional[date], str]:
    """Parse Turkish date formats (DD.MM.YYYY, DD/MM/YYYY, DD-MM-YYYY).
    Returns (parsed_date, error_message)."""
    date_str = date_str.strip()

    formats = [
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d %m %Y",
    ]

    parsed = None
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt).date()
            break
        except ValueError:
            continue

    if not parsed:
        return None, "Tarih formati anlasilamadi. Lutfen GG.AA.YYYY formatinda soyleyin."

    today = date.today()
    if parsed > today:
        return None, "Dogum tarihi gelecekte olamaz."

    if parsed.year < 1900:
        return None, "Gecersiz dogum yili."

    age = (today - parsed).days // 365
    if age < 18:
        return None, "Basvuru icin 18 yasindan buyuk olmalisiniz."

    return parsed, ""
