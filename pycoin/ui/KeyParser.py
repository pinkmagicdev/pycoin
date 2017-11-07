
import binascii
import struct

from pycoin import encoding
from pycoin.key.BIP32Node import BIP32Node
from pycoin.key.Key import Key
from pycoin.key.electrum import ElectrumWallet
from pycoin.contrib.segwit_addr import bech32_decode
from pycoin.serialize import b2h, h2b


class KeyParser(object):
    def __init__(self, ui_context, generator):
        self._ui_context = ui_context
        self._key_class = Key.make_subclass(default_ui_context=ui_context)
        self._bip32node_class = BIP32Node.make_subclass(default_ui_context=ui_context)
        self._electrum_class = ElectrumWallet.make_subclass(default_ui_context=ui_context)
        self._generator = generator

    def key_from_text(self, text):
        key_info = self.key_info_from_text(text)
        if key_info:
            return key_from_key_info(key_info)

    def key_info_from_text(self, text):
        try:
            data = encoding.a2b_hashed_base58(text)
            return self.key_info_from_b58(data)
        except encoding.EncodingError:
            pass

        try:
            hrp, data = bech32_decode(text)
            if hrp and data:
                return self.key_info_from_bech32(hrp, data)
        except (TypeError, KeyError):
            pass

        try:
            prefix, rest = text.split(":", 1)
            data = h2b(rest)
            return self.key_info_from_prefixed_hex(prefix, data)
        except (binascii.Error, TypeError, ValueError):
            pass

        return self.key_info_from_plaintext(text)

    def key_info_from_b58(self, data):

        bip32_prv = data.startswith(self._ui_context.bip32_private_prefix())
        bip32_pub = data.startswith(self._ui_context.bip32_public_prefix())
        if bip32_prv or bip32_pub:
            parent_fingerprint, child_index = struct.unpack(">4sL", data[5:13])

            d = dict(generator=self._generator, chain_code=data[13:45],
                     depth=ord(data[4:5]), parent_fingerprint=parent_fingerprint,
                     child_index=child_index)
            if bip32_prv:
                if data[45:46] != b'\0':
                    return None
                d["secret_exponent"] = encoding.from_bytes_32(data[46:])
            else:
                d["public_pair"] = encoding.sec_to_public_pair(data[45:], self._generator)
            return dict(key_class=self._bip32node_class, key_type="bip32", is_private=bip32_prv, kwargs=d)

        if data.startswith(self._ui_context.wif_prefix()):
            data = data[1:]
            is_compressed = (len(data) > 32)
            if is_compressed:
                data = data[:-1]
            se = encoding.from_bytes_32(data)
            kwargs = dict(secret_exponent=se, generator=self._generator,
                          prefer_uncompressed=not is_compressed)
            return dict(key_class=self._key_class, key_type="wif", kwargs=kwargs)

        if data.startswith(self._ui_context._address_prefix):
            kwargs = dict(hash160=data[1:])
            return dict(key_class=self._key_class, key_type="address", kwargs=kwargs)

        return None

    def key_info_from_bech32(self, prefix, blob):
        return None

    def key_info_from_prefixed_hex(self, prefix, data):
        if prefix == 'E' and self._electrum_class:
            if len(data) == 16:
                kwargs = dict(initial_key=b2h(data), generator=self._generator)
                return dict(key_class=self._electrum_class, key_type="elc_seed", kwargs=kwargs)

            if len(data) == 32:
                kwargs = dict(master_private_key=encoding.from_bytes_32(data), generator=self._generator)
                return dict(key_class=self._electrum_class, key_type="elc_prv", kwargs=kwargs)

            if len(data) == 64:
                kwargs = dict(master_public_key=data, generator=self._generator)
                return dict(key_class=self._electrum_class, key_type="elc_pub", kwargs=kwargs)

        if prefix == 'H' and self._bip32node_class:
            # BRAIN DAMAGE
            import hashlib
            import hmac
            I64 = hmac.HMAC(key=b"Bitcoin seed", msg=data, digestmod=hashlib.sha512).digest()
            kwargs = dict(generator=self._generator, chain_code=I64[32:], secret_exponent=encoding.from_bytes_32(I64[:32]))
            return dict(key_class=self._bip32node_class, key_type="bip32", is_private=True, kwargs=kwargs)

        return None

    def key_info_from_text(self, text):
        if text.startswith("P:") and self._bip32node_class:
            # BRAIN DAMAGE
            import hashlib
            import hmac
            master_secret = text[2:].encode("utf8")
            I64 = hmac.HMAC(key=b"Bitcoin seed", msg=master_secret, digestmod=hashlib.sha512).digest()
            kwargs = dict(generator=self._generator, chain_code=I64[32:], secret_exponent=encoding.from_bytes_32(I64[:32]))
            return dict(key_class=self._bip32node_class, key_type="bip32", is_private=True, kwargs=kwargs)

        return None


def key_from_key_info(key_info):
    return key_info["key_class"](**key_info["kwargs"])
