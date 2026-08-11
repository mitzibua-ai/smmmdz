"""PHPKobo-style HTML obfuscator (compatible output with https://www.phpkobo.com/html-obfuscator)."""

from __future__ import annotations

import random
import re
from datetime import datetime, timezone
from urllib.parse import quote


def _build_char_codes(p12: int, p13: int) -> list[int]:
    char_codes = [0] * 256
    p16 = p13
    for p15 in range(256):
        char_codes[p16] = p15
        p16 = (p16 + p12) % 256
    return char_codes


def encode_html(html: str, *, p9: int | None = None, p12: int | None = None, p13: int | None = None) -> str:
    """Encode HTML using the PHPKobo hex stream cipher."""
    p12 = p12 if p12 is not None else random.randint(1, 255)
    p13 = p13 if p13 is not None else random.randint(0, 255)
    p9 = p9 if p9 is not None else random.randint(0, 0xFFFF)
    char_codes = _build_char_codes(p12, p13)

    encoded_uri = quote(html, safe="")
    bytes_list: list[int] = []
    i = 0
    while i < len(encoded_uri):
        if encoded_uri[i] == "%" and i + 2 < len(encoded_uri):
            bytes_list.append(int(encoded_uri[i + 1 : i + 3], 16))
            i += 3
        else:
            bytes_list.append(ord(encoded_uri[i]))
            i += 1

    hex_pairs: list[str] = []
    for idx, byte_val in enumerate(bytes_list):
        p16 = idx % 256
        hex_val = (byte_val + char_codes[p16]) % 256
        pair = f"{hex_val:02x}"
        pair = pair.replace("e", "X").replace("b", "Y")
        hex_pairs.append(pair)

    suffix = f"{p9:04x}{p12:02x}{p13:02x}"
    return "".join(hex_pairs) + suffix


def _rand_ident(length: int = 12) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    digit = "0123456789"
    first = random.choice(alphabet + "_")
    rest = "".join(random.choice(alphabet + digit + "_") for _ in range(length - 1))
    return first + rest


def build_phpkobo_script(html: str, *, remove_scripts: bool = True, remove_comments: bool = True) -> str:
    """Build PHPKobo-style obfuscated JavaScript that document.write()s HTML at runtime."""
    encoded = encode_html(html)
    remove_scripts_flag = "1" if remove_scripts else "0"
    remove_comments_flag = "1" if remove_comments else "0"

    inner = f"""
(function(){{
"use strict";
var d=document,w=window,html="";
var s=d.currentScript;
if(s&&s.parentNode){{s.parentNode.removeChild(s);}}
d.addEventListener("DOMContentLoaded",function(){{
 if(parseInt("{remove_scripts_flag}")){{
  d.querySelectorAll("script").forEach(function(n){{if(n.parentNode)n.parentNode.removeChild(n);}});
 }}
 if(parseInt("{remove_comments_flag}")){{
  var tw=d.createTreeWalker(d.documentElement,128,null,false),n;
  while((n=tw.nextNode())){{if(n.parentNode)n.parentNode.removeChild(n);}}
 }}
}});
if(!("currentScript" in d)){{return;}}
if("prototype" in d.write){{return;}}
var p4={encoded!r};
var p11=p4.substring(p4.length-8);
var p12=parseInt(p11.substring(4,6),16);
var p13=parseInt(p11.substring(6,8),16);
p4=p4.substring(0,p4.length-8);
p4=p4.replace(/X/gi,"e").replace(/Y/gi,"b").replace(/[^0-9a-f]/gi,"0");
var charCodes=new Array(256),p15=0,p16=p13;
for(;p15<256;p15++,p16=(p16+p12)%256){{charCodes[p16]=p15;}}
var p17=p4.match(/.{{2}}/g)||[],encoded=[],p16=0;
for(p15=0;p15<p17.length;p15++,p16=(p16+1)%256){{
 var p19=(parseInt(p17[p15],16)-charCodes[p16]+256)%256;
 encoded.push("%"+(p19<16?"0":"")+p19.toString(16));
}}
html=w.decodeURIComponent(encoded.join(""));
if(!html){{return;}}
d.open("text/html","replace");
d.write(html);
d.close();
}})();
""".strip()

    outer = (
        ";Function('"
        "var r=\\\"\\\\162\\\\145\\\\160\\\\154\\\\141\\\\143\\\\145\\\";"
        "var c=\\\"constructor\\\"[r](/[]/g,\\\"\\\");"
        "var f=this[c];"
        f"f({inner!r})();"
        "')(typeof globalThis!==\\\"undefined\\\"?globalThis:window);"
    )
    return outer


def build_phpkobo_page(html: str, *, remove_scripts: bool = True, remove_comments: bool = True) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    script = build_phpkobo_script(html, remove_scripts=remove_scripts, remove_comments=remove_comments)
    return (
        f"<!-- Obfuscated at {stamp} on https://www.phpkobo.com/html-obfuscator -->"
        f"<!DOCTYPE html><meta charset=\"UTF-8\"><script>{script}</script>"
    )


def prepare_full_html(text: str) -> str:
    text = re.sub(r"<!--(?!.*\[if).*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r">\s+<", "><", text)
    return text.strip()
