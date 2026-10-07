"""Lossless Starfield text patching primitives. No filesystem writes here."""
import re,struct,zlib
from collections import Counter

class PatchError(ValueError):pass
CONTROL_PATTERN=r'\[(?:Accept|Activate|DataMenu|Cancel|XButton|Monocle|Confirm|SelectTarget|Jump|LShoulder|RShoulder|RTrigger|WeaponGroup[123]|Move|StrafeLeft|StrafeRight|Forward|Back|TogglePOV|Sneak|PrimaryAttack|SecondaryAttack|LeftStick|RepairShip|Click|QuickInventory|Boosters|Sprint|AltAttack|ExecuteJump|Edit|ToggleView|PlaceBeacon|ZoomIn|Look|WeaponReadyReload|RotateLock|VATS|RightStick|Quickkey10|QuickkeyDown|PlaceMarker|TakeOff|SHMonocle|ShipBuilder|FlightCheck|MoveUp|MoveDown|ApplyCritical|StartWait|CargoHold|ShipTransaction|FastTravelShip|RotatePick|ReadyWeapon|LTrigger|Mouse2|NextTarget|PrevTarget|_Dpad_None|L3|R3|ChangeMode)(?::\d+)?\]'

def decode_text(raw):
    try:return raw.decode('utf-8')
    except UnicodeDecodeError:return raw.decode('cp1252')

def translation_tokens(text):
    tokens=re.findall(r'<[^>]+>|%\d*\$?[sdif]|\{\d+\}',text)
    # Book image captions are display text. Protect the image name and all other
    # attributes while allowing only the quoted caption value to be localized.
    return Counter(re.sub(r"(\bcaption\s*=\s*)(['\"])(.*?)\2",lambda m:m[1]+m[2]+'__CAPTION__'+m[2],token)
                   if re.match(r'<image\b',token,re.I) else token for token in tokens)

def check_translation(source,translation):
    if not translation or '\0' in translation:raise PatchError('Empty/NUL translation')
    if translation_tokens(source)!=translation_tokens(translation):
        raise PatchError('Placeholder mismatch')
    if source.count('\n')!=translation.count('\n'):raise PatchError('Newline mismatch')
    if re.search(r'\b(?:press|hold|holding|using|controls|key|button)\b',source,re.I):
        if Counter(re.findall(CONTROL_PATTERN,source))!=Counter(re.findall(CONTROL_PATTERN,translation)):
            raise PatchError('Control token mismatch')
    return translation.encode('utf-8')+b'\0'

def field_spans(body):
    pos=0;indices=Counter()
    while pos<len(body):
        begin=pos;extended=None
        if pos+6>len(body):raise PatchError('Truncated field')
        name=body[pos:pos+4];length=struct.unpack_from('<H',body,pos+4)[0];pos+=6
        if name==b'XXXX':
            if length!=4 or pos+4>len(body):raise PatchError('Invalid XXXX')
            extended=struct.unpack_from('<I',body,pos)[0];pos+=4
            if pos+6>len(body):raise PatchError('Missing extended field')
            name=body[pos:pos+4];pos+=6;length=extended
        if pos+length>len(body):raise PatchError('Field outside record')
        index=indices[name];indices[name]+=1
        end=pos+length
        yield name.decode('ascii'),index,body[pos:end],body[begin:end]
        pos=end

def encode_field(name,value):
    name=name.encode('ascii');length=len(value)
    if length>65535:return b'XXXX\x04\0'+struct.pack('<I',length)+name+b'\0\0'+value
    return name+struct.pack('<H',length)+value

def patch_plugin(data,translations):
    """Map (record, FormID integer, field, index) to (source, translation)."""
    changed=[];seen=set()
    record_targets={}
    for key,value in translations.items():record_targets.setdefault(key[:2],{})[key]=value
    if len(data)<24 or data[:4]!=b'TES4':raise PatchError('Not a plugin')
    if struct.unpack_from('<I',data,8)[0]&0x80 and translations:
        raise PatchError('Localized plugin fields require Strings routing')
    def walk(start,end):
        output=[];pos=start
        while pos<end:
            if pos+24>end:raise PatchError('Truncated record header')
            header=data[pos:pos+24];record=header[:4].decode('ascii')
            size=struct.unpack_from('<I',header,4)[0]
            if record=='GRUP':
                if size<24 or pos+size>end:raise PatchError('Invalid group size')
                inner=walk(pos+24,pos+size)
                value=header[:4]+struct.pack('<I',24+len(inner))+header[8:]+inner
                output.append(value);pos+=size;continue
            finish=pos+24+size
            if finish>end:raise PatchError('Record outside group')
            flags,fid=struct.unpack_from('<II',header,8)
            payload=data[pos+24:finish];raw_record=data[pos:finish];pos=finish
            wanted=record_targets.get((record,fid),{})
            if not wanted or flags&0x20:output.append(raw_record);continue
            compressed=bool(flags&0x40000)
            if compressed:
                if len(payload)<4:raise PatchError('Truncated compressed record')
                body=zlib.decompress(payload[4:])
                if len(body)!=struct.unpack_from('<I',payload)[0]:raise PatchError('Decompressed size mismatch')
            else:body=payload
            pieces=[];record_changed=False
            for field,index,value,original in field_spans(body):
                key=(record,fid,field,index)
                if key not in wanted:pieces.append(original);continue
                if key in seen:raise PatchError('Duplicate target record/field')
                seen.add(key);spec=wanted[key];source,translation=spec[:2]
                if not value.endswith(b'\0'):raise PatchError('Nonterminated text field')
                if len(spec)==3:
                    if value[:-1]!=bytes.fromhex(spec[2]):raise PatchError('Raw source changed since extraction')
                elif decode_text(value[:-1])!=source:raise PatchError('Source changed since extraction')
                if source==translation:pieces.append(original);continue
                new=check_translation(source,translation)
                pieces.append(encode_field(field,new));record_changed=True;changed.append(key)
            if not record_changed:output.append(raw_record);continue
            newbody=b''.join(pieces)
            newpayload=struct.pack('<I',len(newbody))+zlib.compress(newbody) if compressed else newbody
            output.append(header[:4]+struct.pack('<I',len(newpayload))+header[8:]+newpayload)
        return b''.join(output)
    result=walk(0,len(data))
    if seen!=set(translations):raise PatchError('Some translation targets were not found')
    return result,changed

def read_strings(raw,kind):
    if kind not in ('.strings','.dlstrings','.ilstrings'):raise PatchError('Unknown Strings kind')
    if len(raw)<8:raise PatchError('Truncated Strings header')
    count,size=struct.unpack_from('<II',raw);start=8+count*8
    if start+size!=len(raw):raise PatchError('Strings payload size mismatch')
    entries=[];seen=set()
    for i in range(count):
        sid,offset=struct.unpack_from('<II',raw,8+8*i);pos=start+offset
        if sid in seen or pos>=len(raw):raise PatchError('Invalid/duplicate String ID')
        seen.add(sid)
        if kind=='.strings':
            end=raw.index(b'\0',pos)+1;block=raw[pos:end];value=block[:-1]
        else:
            if pos+4>len(raw):raise PatchError('Truncated string length')
            length=struct.unpack_from('<I',raw,pos)[0];end=pos+4+length
            if length<1 or end>len(raw) or raw[end-1]!=0:raise PatchError('Invalid length-prefixed string')
            block=raw[pos:end];value=block[4:-1]
        entries.append((sid,decode_text(value),block))
    return entries

def patch_strings(raw,kind,translations):
    entries=read_strings(raw,kind);directory=[];blocks=[];offset=0;changed=[];seen=set()
    for sid,source,block in entries:
        if sid in translations:
            seen.add(sid);expected,translation=translations[sid]
            if source!=expected:raise PatchError('Strings source changed since extraction')
            if source!=translation:
                encoded=check_translation(source,translation)
                block=encoded if kind=='.strings' else struct.pack('<I',len(encoded))+encoded
                changed.append(sid)
        directory.append(struct.pack('<II',sid,offset));blocks.append(block);offset+=len(block)
    if seen!=set(translations):raise PatchError('Missing String ID')
    if not changed:return raw,changed
    return struct.pack('<II',len(entries),offset)+b''.join(directory)+b''.join(blocks),changed
