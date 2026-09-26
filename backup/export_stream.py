"""
Shared `db_export.json` streaming reader -- Story 2.3, extracted in Story 2.4
so `backup/restore_apply.py`'s restore-apply path and
`backup/restore_validation.py`'s Stage 6 (date-scoped match) import one
implementation, never two.

`ExportReader` streams `db_export.json` -- `{"<model key>": [<record>, ...],
...}` -- from a binary file-like object without ever holding more than the
current buffer and one record. Nothing here touches any domain model; it only
decodes JSON.
"""
import codecs
import json

from backup import restore_validation
from backup.services import COPY_CHUNK_SIZE

_clip = restore_validation._clip

# A single record larger than this is not a real record (defends `_decode`
# against being made to buffer forever on a malformed/adversarial file).
MAX_RECORD_CHARS = 64 * 1024 * 1024


class ExportFormatError(Exception):
    """`db_export.json` is malformed or holds records this restore refuses."""

    def __init__(self, message, audit_message=None):
        super().__init__(message)
        self.message = message
        # Story 2.6: a value-free variant for the audit record, when `message`
        # quotes archive data (e.g. a patient identifier).
        self.audit_message = audit_message


class _Start:
    def __repr__(self):
        return 'START'


START = _Start()  # yielded in place of a record when a model's array begins

_RAW_DECODE = json.JSONDecoder().raw_decode
_WHITESPACE = ' \t\r\n'


class ExportReader:
    """
    Streams `db_export.json` -- `{"<model key>": [<record>, ...], ...}` --
    from a binary file-like object without ever holding more than the current
    buffer and one record. Iterating yields `(key, START)` when a model's
    array begins and `(key, record)` for each record in it; the records of
    `skip_keys` are decoded and dropped (never yielded, never retained).
    `bytes_read` is the uncompressed byte count consumed so far (for progress).

    Records are decoded with `json.JSONDecoder.raw_decode` on a text buffer
    that is refilled when a value is cut off by its end; a value that is still
    undecodable after `MAX_RECORD_CHARS` is malformed, not just large.
    """

    def __init__(self, stream, skip_keys=()):
        self._stream = stream
        self._skip = frozenset(skip_keys)
        self._decoder = codecs.getincrementaldecoder('utf-8')()
        self._buf = ''
        self._pos = 0
        self._eof = False
        self.bytes_read = 0

    @staticmethod
    def _bad(message):
        raise ExportFormatError(f"db_export.json is malformed: {message}.")

    def _fill(self, size=COPY_CHUNK_SIZE):
        """Read and append more text (dropping what was already consumed).
        Returns False at the end of the stream."""
        if self._eof:
            return False
        try:
            data = self._stream.read(size)
            text = self._decoder.decode(data, final=not data)
        except UnicodeDecodeError:
            self._bad("it is not valid UTF-8")
        except restore_validation._ZIP_READ_ERRORS as e:
            raise ExportFormatError(f"db_export.json could not be read from the archive ({_clip(e, 100)}).")
        self.bytes_read += len(data)
        self._buf = self._buf[self._pos:] + text
        self._pos = 0
        if not data:
            self._eof = True
            return False
        return True

    def _peek(self):
        """The next non-whitespace character ('' at the end of the stream)."""
        while True:
            buf, pos = self._buf, self._pos
            while pos < len(buf) and buf[pos] in _WHITESPACE:
                pos += 1
            self._pos = pos
            if pos < len(buf):
                return buf[pos]
            if not self._fill():
                return ''

    def _expect(self, char):
        if self._peek() != char:
            self._bad(f"expected '{char}' at byte {self.bytes_read}")
        self._pos += 1

    def _decode(self):
        """One JSON value starting at the next non-whitespace character."""
        if self._peek() == '':
            self._bad("the file ends unexpectedly")
        while True:
            try:
                value, end = _RAW_DECODE(self._buf, self._pos)
            except RecursionError:
                self._bad("a record is nested too deeply")
            except json.JSONDecodeError:
                pending = len(self._buf) - self._pos
                if pending > MAX_RECORD_CHARS or not self._fill(max(COPY_CHUNK_SIZE, pending)):
                    self._bad(f"invalid JSON near byte {self.bytes_read}")
                continue
            self._pos = end
            return value

    def __iter__(self):
        self._expect('{')
        if self._peek() == '}':
            self._pos += 1
        else:
            while True:
                key = self._decode()
                if not isinstance(key, str):
                    self._bad("a model key is not a string")
                self._expect(':')
                self._expect('[')
                yield key, START
                skipping = key in self._skip
                if self._peek() == ']':
                    self._pos += 1
                else:
                    while True:
                        record = self._decode()
                        if not skipping:
                            yield key, record
                        char = self._peek()
                        self._pos += 1
                        if char == ']':
                            break
                        if char != ',':
                            self._bad(f"expected ',' or ']' after a record of '{_clip(key, 40)}'")
                char = self._peek()
                self._pos += 1
                if char == '}':
                    break
                if char != ',':
                    self._bad("expected ',' or '}' after a model's records")
        if self._peek() != '':
            self._bad("unexpected data after the closing '}'")


def iter_export_records(stream, skip_keys=()):
    """`ExportReader` over `stream`. `skip_keys` -- model keys whose records
    are decoded and dropped rather than yielded (each caller passes its own:
    `restore_apply` skips the referral models, `restore_validation`'s Stage 6
    skips everything except `patients.patient`)."""
    return ExportReader(stream, skip_keys=skip_keys)
