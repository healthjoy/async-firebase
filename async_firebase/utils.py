import io
import typing as t
from copy import deepcopy
from dataclasses import fields, is_dataclass
from email.generator import Generator
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart


def remove_null_values(dict_value: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    """Remove Falsy values from the dictionary."""
    return {k: v for k, v in dict_value.items() if v not in [None, [], {}]}


def cleanup_firebase_message(dataclass_obj, dict_factory: t.Callable = dict) -> dict:
    """
    The instrumentation to cleanup firebase message from null values.

    Example::

        considering following dataclass

        msg = Message(
            token='qwe',
            data={},
            notification=Notification(title='push-title', body='push-body'),
            android=None,
            webpush={},
            apns=APNSConfig(
                headers={'hdr': 'qwe'},
                payload=APNSPayload(
                    aps=Aps(
                        alert=None,
                        badge=None,
                        sound='generic',
                        content_available=None,
                        category=None,
                        thread_id=None,
                        mutable_content=None,
                        custom_data={}
                    ),
                    custom_data={}
                )
            ),
            topic=None,
            condition=None
        )

        >>> dataclass_to_dict_remove_null_values(msg)
        {
            'token': 'qwe',
            'notification': {'title': 'push-title', 'body': 'push-body'},
            'apns': {
                'headers': {'hdr': 'qwe'},
                'payload': {
                    'aps': {'sound': 'generic'}
                }
            }
        }

    :param dataclass_obj: instance of dataclass. This suppose to be instance of ``messages.PushNotification`` or
        ``messages.Message``.
    :param dict_factory: if given, ``dict_factory`` will be used instead of built-in dict.
        The function applies recursively to field values that are dataclass instances.
    :return: the fields of a dataclass instance as a new dictionary mapping field names to field values.
    """
    if is_dataclass(dataclass_obj):
        result = []
        for f in fields(dataclass_obj):
            value = cleanup_firebase_message(getattr(dataclass_obj, f.name), dict_factory)
            result.append((f.name, value))
        return remove_null_values(dict_factory(result))
    elif isinstance(dataclass_obj, (list, tuple)):
        return type(dataclass_obj)(cleanup_firebase_message(v, dict_factory) for v in dataclass_obj)  # type: ignore
    elif isinstance(dataclass_obj, dict):
        return remove_null_values({k: cleanup_firebase_message(v, dict_factory) for k, v in dataclass_obj.items()})
    return deepcopy(dataclass_obj)


def serialize_mime_message(
    message: t.Union[MIMEMultipart, MIMENonMultipart], mangle_from: bool = None, max_header_len: int = None
) -> str:
    """
    Serialize the MIME type message.

    :param message: MIME type message
    :param mangle_from: is a flag that, when True (the default if policy
        is not set), escapes From_ lines in the body of the message by putting
        a `>' in front of them.
    :param max_header_len: specifies the longest length for a non-continued
        header.  When a header line is longer (in characters, with tabs
        expanded to 8 spaces) than max_header_len, the header will split as
        defined in the Header class.  Set max_header_len to zero to disable
        header wrapping. The default is 78, as recommended (but not required)
        by RFC 2822.
    :return: the entire contents of the object.
    """
    fp = io.StringIO()
    gen = Generator(fp, mangle_from_=mangle_from, maxheaderlen=max_header_len)
    gen.flatten(message, unixfrom=False)
    return fp.getvalue()
