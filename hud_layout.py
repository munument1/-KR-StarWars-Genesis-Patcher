"""Apply source-guarded HUD tag replacements without rewriting other SWF tags."""
import base64,hashlib,struct,zlib
from preserve_font_resources import tags_bytes

def patch_hud(raw,recipe):
    edits={(r['tag'],r['id']):r for r in recipe['replacements']};seen=set();out=[]
    for tag,body in tags_bytes(raw):
        key=(tag,struct.unpack_from('<H',body)[0]) if tag in (37,39) else None
        if key in edits:
            r=edits[key]
            if key in seen or hashlib.sha256(body).hexdigest()!=r['input_sha256']:raise ValueError('Unexpected HUD tag')
            seen.add(key);body=base64.b64decode(r['body'])
        size=len(body);out.append(struct.pack('<H',(tag<<6)|size) if size<63 else struct.pack('<HI',(tag<<6)|63,size));out.append(body)
    if seen!=set(edits):raise ValueError('HUD tags missing')
    data=raw[:8]+zlib.decompress(raw[8:]) if raw[:3] in (b'CWS',b'CFX') else raw
    bits=data[8]>>3;start=8+(5+4*bits+7)//8+4;payload=data[8:start]+b''.join(out)
    header=raw[:4]+struct.pack('<I',len(payload)+8)
    return header+(zlib.compress(payload,9) if raw[:3] in (b'CWS',b'CFX') else payload)
