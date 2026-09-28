"""Every message Karibu can send, in one place.

Host messages go out over SMS to a basic phone, so they must survive two hard
limits: one 160-character GSM-7 segment, and a reader who may not read well.
That is why each of them ends in a numbered choice. Visitor messages travel
over the web page and can be longer.
"""

from __future__ import annotations

# GSM 03.38 basic character set plus the extension characters we allow.
# A message built only from these costs one SMS segment instead of two.
GSM7 = set(
    "@£$¥èéùìòÇ\nØø\rÅå"
    "Δ_ΦΓΛΩΠΨΣΘΞÆæßÉ"
    " !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"
)

SMS_SEGMENT = 160

MONTHS_FR = [
    "janv", "fevr", "mars", "avr", "mai", "juin",
    "juil", "aout", "sept", "oct", "nov", "dec",
]

TEMPLATES: dict[str, dict[str, str]] = {
    # --- host side, French, one SMS segment ---
    "host_request": {
        "fr": ("Karibu: demande {nights}n {stay}, {guests} pers{meal}. "
               "Total {total} {cur}. Repondre 1=OUI 2=NON 3=AUTRE DATE"),
    },
    "host_reprompt": {
        "fr": ("Karibu: reponse non comprise. Repondre par un seul chiffre. "
               "1=OUI 2=NON 3=AUTRE DATE"),
    },
    "host_confirmed_ack": {
        "fr": ("Karibu: reservation {ref} confirmee. {stay}, {guests} pers, "
               "{total} {cur}. Paiement a l'arrivee."),
    },
    "host_declined_ack": {
        "fr": "Karibu: demande {ref} refusee. Le visiteur est prevenu.",
    },
    "host_alt_ack": {
        "fr": ("Karibu: vous proposez d'autres dates pour {ref}. "
               "Le visiteur est prevenu et va repondre."),
    },
    "host_reminder": {
        "fr": ("Karibu: arrivee demain {arrival}, {guests} pers ({visitor}). "
               "Repondre 9 pour annuler."),
    },
    "host_cancel_ack": {
        "fr": "Karibu: reservation {ref} annulee. Le visiteur est prevenu.",
    },
    "host_expired": {
        "fr": ("Karibu: demande {ref} expiree, pas de reponse en {hours}h. "
               "Le visiteur cherche ailleurs."),
    },
    "host_listing_created": {
        "fr": ("Karibu: annonce creee. {rooms} chambre(s), {price} {cur}/nuit"
               "{meal}, {place}. Repondre 1=OK 2=CORRIGER"),
    },
    # --- visitor side, web page, any length ---
    "visitor_pending": {
        "en": ("Request sent to the host. They answer from a basic phone, so "
               "allow up to {hours} hours. You will see the answer here."),
        "ko": ("호스트에게 요청을 보냈습니다. "
               "일반 휴대폰으로 답하므로 최대 {hours}시간 "
               "걸릴 수 있습니다. 답변은 여기에 표시됩니다."),
        "fr": ("Demande envoyee a l'hote. Il repond depuis un telephone simple, "
               "comptez jusqu'a {hours} heures. La reponse s'affichera ici."),
    },
    "visitor_confirmed": {
        "en": ("Confirmed. {stay}, {guests} guest(s){meal}, {total} {cur}. "
               "Reference {ref}. Pay on arrival by mobile money."),
        "ko": ("확정되었습니다. {stay}, {guests}명{meal}, "
               "{total} {cur}. 예약번호 {ref}. 도착 시 "
               "모바일머니로 결제하세요."),
        "fr": ("Confirme. {stay}, {guests} pers{meal}, {total} {cur}. "
               "Reference {ref}. Paiement mobile money a l'arrivee."),
    },
    "visitor_declined": {
        "en": "The host is not available for those dates. Try other dates or another host.",
        "ko": ("호스트가 해당 날짜에 여유가 없습니다. "
               "다른 날짜나 다른 숙소를 이용해 주세요."),
        "fr": "L'hote n'est pas disponible a ces dates. Essayez d'autres dates ou un autre hote.",
    },
    "visitor_alt_date": {
        "en": "The host is free on other dates and will send a proposal shortly.",
        "ko": "호스트가 다른 날짜를 제안할 예정입니다.",
        "fr": "L'hote propose d'autres dates et vous les envoie sous peu.",
    },
    "visitor_expired": {
        "en": "No answer from the host within {hours} hours. Nothing was booked.",
        "ko": "{hours}시간 내에 호스트 답변이 없었습니다. 예약되지 않았습니다.",
        "fr": "Pas de reponse de l'hote en {hours} heures. Rien n'a ete reserve.",
    },
    "visitor_cancelled": {
        "en": "The host cancelled booking {ref}. You are not charged.",
        "ko": "호스트가 예약 {ref}을(를) 취소했습니다. 요금은 청구되지 않습니다.",
        "fr": "L'hote a annule la reservation {ref}. Rien ne vous est facture.",
    },
}


def render(key: str, lang: str, params: dict) -> str:
    """Return one message. Falls back to English, then French, then any language."""
    variants = TEMPLATES[key]
    for candidate in (lang, "en", "fr"):
        if candidate in variants:
            return variants[candidate].format(**params)
    return next(iter(variants.values())).format(**params)


def is_gsm7(text: str) -> bool:
    """True when the text costs a single SMS segment on a basic phone."""
    return all(char in GSM7 for char in text)


def fits_one_sms(text: str) -> bool:
    return is_gsm7(text) and len(text) <= SMS_SEGMENT


def format_stay(check_in, nights: int) -> str:
    """Short French date range: '12-14 oct' or '30 sept-2 oct'."""
    from datetime import timedelta

    check_out = check_in + timedelta(days=nights)
    if check_in.month == check_out.month:
        return f"{check_in.day}-{check_out.day} {MONTHS_FR[check_in.month - 1]}"
    return (
        f"{check_in.day} {MONTHS_FR[check_in.month - 1]}"
        f"-{check_out.day} {MONTHS_FR[check_out.month - 1]}"
    )


def format_day(day) -> str:
    return f"{day.day} {MONTHS_FR[day.month - 1]}"


def format_money(amount: int) -> str:
    """No thousands separator: it costs characters and confuses SMS displays."""
    return str(int(amount))
