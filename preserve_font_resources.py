"""Combine converted Korean outlines with original font glyphs and UI resources."""
import struct,zlib
from pathlib import Path
def tags_bytes(data):
    if data[:3] in (b'CWS',b'CFX'):data=data[:8]+zlib.decompress(data[8:])
    bits=data[8]>>3;pos=8+(5+4*bits+7)//8+4;result=[]
    while pos+2<=len(data):
        h=struct.unpack_from('<H',data,pos)[0];pos+=2;tag=h>>6;n=h&63
        if n==63:n=struct.unpack_from('<I',data,pos)[0];pos+=4
        result.append((tag,data[pos:pos+n]));pos+=n
        if not tag:break
    if pos!=len(data):raise ValueError('Unexpected SWF trailing bytes')
    return result
def tags(path):return tags_bytes(path.read_bytes())

def decode_font(body):
    flags=body[2];ln=body[4];num=struct.unpack_from('<H',body,5+ln)[0];start=7+ln
    width=4 if flags&8 else 2;fmt='<I' if width==4 else '<H'
    offsets=[struct.unpack_from(fmt,body,start+i*width)[0] for i in range(num+1)]
    codepos=start+offsets[-1];cw=2 if flags&4 else 1
    codes=[struct.unpack_from('<H' if cw==2 else '<B',body,codepos+i*cw)[0] for i in range(num)]
    glyphs={c:{'shape':body[start+offsets[i]:start+offsets[i+1]]} for i,c in enumerate(codes)}
    pos=codepos+num*cw;metrics=kerning=b''
    if flags&128:
        metrics=body[pos:pos+6];pos+=6
        for c in codes:glyphs[c]['advance']=body[pos:pos+2];pos+=2
        for c in codes:
            bits=body[pos]>>3;n=(5+4*bits+7)//8
            glyphs[c]['bounds']=body[pos:pos+n];pos+=n
        if not flags&4:raise ValueError('Narrow original kerning codes unsupported')
        kerning=body[pos:]
    elif pos!=len(body):raise ValueError('Unexpected data after font codes')
    return {'prefix':body[:5+ln],'flags':flags,'glyphs':glyphs,'metrics':metrics,'kerning':kerning}

def korean(c):
    return 0xAC00<=c<=0xD7A3 or 0x1100<=c<=0x11ff or 0x3130<=c<=0x318f or 0xA960<=c<=0xA97f or 0xD7B0<=c<=0xD7ff

def merge_font(original,converted):
    return add_glyphs(original,decode_font(converted)['glyphs'])

def add_glyphs(original,additions):
    old=decode_font(original);glyphs=dict(old['glyphs'])
    for c,r in additions.items():
        if korean(c) and c not in glyphs:glyphs[c]=r
    codes=sorted(glyphs);prefix=bytearray(old['prefix']);prefix[2]|=12
    offset=4*(len(codes)+1);offsets=[];shapes=[]
    for c in codes:
        shape=glyphs[c]['shape'];offsets.append(offset);shapes.append(shape);offset+=len(shape)
    offsets.append(offset)
    body=bytes(prefix)+struct.pack('<H',len(codes))+b''.join(struct.pack('<I',o) for o in offsets)+b''.join(shapes)+b''.join(struct.pack('<H',c) for c in codes)
    if old['flags']&128:
        body+=old['metrics']+b''.join(glyphs[c]['advance'] for c in codes)+b''.join(glyphs[c]['bounds'] for c in codes)+old['kerning']
    return body

def preserve(source,converted,destination,selected):
    newfonts={struct.unpack_from('<H',b)[0]:b for t,b in tags(converted) if t==75}
    result,removed=patch_font_bytes(source.read_bytes(),{fid:decode_font(newfonts[fid])['glyphs'] for fid in selected})
    destination.write_bytes(result)
    return removed

def patch_font_bytes(raw,additions):
    original_tags=tags_bytes(raw)
    if any(t in (11,33) for t,b in original_tags):raise ValueError('Static text glyph references require explicit remapping')
    out=[];removed=[]
    for t,b in original_tags:
        fid=struct.unpack_from('<H',b)[0] if t in (75,73) else None
        if t==75 and fid in additions:b=add_glyphs(b,additions[fid])
        elif t==73 and fid in additions:
            # Old alignment tables have one entry per original glyph and cannot
            # be retained after adding glyphs; FFDec also removes these tables.
            removed.append(fid);continue
        n=len(b);out.append(struct.pack('<H',(t<<6)|n) if n<63 else struct.pack('<HI',(t<<6)|63,n));out.append(b)
    data=raw[:8]+zlib.decompress(raw[8:]) if raw[:3] in (b'CWS',b'CFX') else raw
    bits=data[8]>>3;start=8+(5+4*bits+7)//8+4
    payload=data[8:start]+b''.join(out)
    header=raw[:4]+struct.pack('<I',len(payload)+8)
    return header+(zlib.compress(payload,9) if raw[:3] in (b'CWS',b'CFX') else payload),removed
