from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime, timezone

from flask import Response

from timApp.util.flask.responsehelper import ok_response, json_response
from timApp.util.flask.typedblueprint import TypedBlueprint

timMessage = TypedBlueprint('timMessage', __name__, url_prefix='/timMessage')

@dataclass
class MessageOptions:
    #Options regarding TIM messages
    recipients: List[str] # VIESTIM: find recipient by email or some other identifier?
    messageSubject: str
    messageBody: str
    messageChannel: bool
    important: bool
    isPrivate: bool
    archive: bool
    pageList: str
    readReceipt: bool
    reply: bool
    sender: str
    senderEmail: str
    expires: Optional[datetime] = None

@timMessage.route("/send", methods=['POST'])
def send_tim_message(options: MessageOptions) -> Response:
    #TODO: actual logic, this is just a placeholder
    print(options)
    return ok_response()