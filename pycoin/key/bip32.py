# -*- coding: utf-8 -*-
"""
A BIP0032-style hierarchical wallet.

Implement a BIP0032-style hierarchical wallet which can create public
or private wallet keys. Each key can create many child nodes. Each node
has a wallet key and a corresponding private & public key, which can
be used to generate Bitcoin addresses or WIF private keys.

At any stage, the private information can be stripped away, after which
descendants can only produce public keys.

Private keys can also generate "hardened" children, which cannot be
generated by the corresponding public keys. This is useful for generating
"change" addresses, for example, which there is no need to share with people
you give public keys to.


The MIT License (MIT)

Copyright (c) 2013 by Richard Kiss

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import hashlib
import hmac
import struct

from .. import ecdsa

from ..encoding import public_pair_to_sec, from_bytes_32, to_bytes_32
from ..ecdsa.ellipticcurve import INFINITY

ORDER = ecdsa.generator_secp256k1.order()


def subkey_secret_exponent_chain_code_pair(
        secret_exponent, chain_code_bytes, i, is_hardened, public_pair=None):
    """
    Yield info for a child node for this node.

    secret_exponent:
        base secret exponent
    chain_code:
        base chain code
    i:
        the index for this node.
    is_hardened:
        use "hardened key derivation". The public version of this node cannot calculate this child.
    public_pair:
        the public_pair for the given secret exponent. If you leave it None, it's calculated for you
        (but then it's slower)

    Returns a pair (new_secret_exponent, new_chain_code)
    """
    i_as_bytes = struct.pack(">L", i)

    if is_hardened:
        data = b'\0' + to_bytes_32(secret_exponent) + i_as_bytes
    else:
        if public_pair is None:
            public_pair = ecdsa.public_pair_for_secret_exponent(ecdsa.generator_secp256k1, secret_exponent)
        sec = public_pair_to_sec(public_pair, compressed=True)
        data = sec + i_as_bytes

    I64 = hmac.HMAC(key=chain_code_bytes, msg=data, digestmod=hashlib.sha512).digest()
    I_left_as_exponent = from_bytes_32(I64[:32])
    if I_left_as_exponent >= ORDER:
        raise ValueError('I_L >= {}'.format(ORDER))
    new_secret_exponent = (I_left_as_exponent + secret_exponent) % ORDER
    if new_secret_exponent == 0:
        raise ValueError('k_{} == 0'.format(i))
    new_chain_code = I64[32:]
    return new_secret_exponent, new_chain_code


def subkey_public_pair_chain_code_pair(public_pair, chain_code_bytes, i):
    """
    Yield info for a child node for this node.

    public_pair:
        base public pair
    chain_code:
        base chain code
    i:
        the index for this node.

    Returns a pair (new_public_pair, new_chain_code)
    """
    i_as_bytes = struct.pack(">l", i)
    sec = public_pair_to_sec(public_pair, compressed=True)
    data = sec + i_as_bytes

    I64 = hmac.HMAC(key=chain_code_bytes, msg=data, digestmod=hashlib.sha512).digest()

    I_left_as_exponent = from_bytes_32(I64[:32])
    x, y = public_pair

    the_point = I_left_as_exponent * ecdsa.generator_secp256k1 + \
        ecdsa.Point(ecdsa.generator_secp256k1.curve(), x, y, ORDER)
    if the_point == INFINITY:
        raise ValueError('K_{} == {}'.format(i, the_point))

    I_left_as_exponent = from_bytes_32(I64[:32])
    if I_left_as_exponent >= ORDER:
        raise ValueError('I_L >= {}'.format(ORDER))
    new_public_pair = the_point.pair()
    new_chain_code = I64[32:]
    return new_public_pair, new_chain_code
