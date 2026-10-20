"""Minimal MSFT type library dumper (format per Wine's typelib.h).

Usage:
    innoextract staruml-5.0-with-cm.exe          # -> app/StarUML.exe
    7z x app/StarUML.exe -oexe                    # -> exe/.rsrc/0/TYPELIB/1
    python tools/tlbdump.py exe/.rsrc/0/TYPELIB/1 > docs/com-api.txt
"""
import struct, sys
d = open(sys.argv[1], 'rb').read()
i32 = lambda o: struct.unpack_from('<i', d, o)[0]
u16 = lambda o: struct.unpack_from('<H', d, o)[0]
assert d[:4] == b'MSFT'
varflags = i32(0x14); ntypes = i32(0x20)
off = 0x54 + (4 if varflags & 0x100 else 0)
tioffs = [i32(off + 4*k) for k in range(ntypes)]
seg = off + 4*ntypes
segs = [(i32(seg+16*k), i32(seg+16*k+4)) for k in range(15)]
TI, IMPINFO, IMPFILES, REF, GHASH, GUID, NHASH, NAME, STR, TYPDESC = [s[0] for s in segs[:10]]
def name(o):
    if o < 0: return '?'
    p = NAME + o; ln = d[p+8]
    return d[p+12:p+12+ln].decode('latin1')
VT = {0:'empty',2:'short',3:'long',4:'float',5:'double',6:'currency',7:'date',8:'BSTR',9:'IDispatch',10:'SCODE',11:'bool',12:'VARIANT',13:'IUnknown',16:'char',17:'byte',18:'ushort',19:'ulong',20:'int64',22:'int',23:'uint',24:'void',25:'HRESULT',26:'PTR',27:'SAFEARRAY',29:'USERDEF',30:'LPSTR',31:'LPWSTR'}
def tiname(href):
    k = (href & ~3) // 0x64
    return name(i32(TI + k*0x64 + 0x34)) if 0 <= k < ntypes else '?'
def tdesc(t):
    if t < 0 or t & 0x80000000: return VT.get(t & 0xffff & 0x7fff, hex(t & 0xffff))
    p = TYPDESC + t; vt = u16(p) & 0xfff; ref = i32(p+4)
    if vt == 26: return tdesc(ref if ref >= 0 else (ref & 0xffff) | 0x80000000) + '*'
    if vt == 29: return tiname(ref)
    if vt == 27: return 'SAFEARRAY(' + tdesc(ref if ref >= 0 else (ref & 0xffff)|0x80000000) + ')'
    return VT.get(vt, hex(vt))
KINDS = ['enum','record','module','interface','dispatch','coclass','alias','union']
INVK = {1:'',2:'get ',4:'put ',8:'putref '}
for k in range(ntypes):
    b = TI + k*0x64
    kind = i32(b) & 0xf; mo = i32(b+4); ce = i32(b+0x18)
    nf, nv = ce & 0xffff, ce >> 16
    tn = name(i32(b+0x34))
    print(f'\n## {KINDS[kind]} {tn}')
    if mo < 0 or (nf + nv) == 0: continue
    blk = i32(mo); recs = mo + 4; n = nf + nv
    names = [name(i32(recs + blk + 4*n + 4*j)) for j in range(n)]
    memids = [i32(recs + blk + 4*j) for j in range(n)]
    offs = [i32(recs + blk + 8*n + 4*j) for j in range(n)]
    for j in range(nf):
        r = recs + offs[j]; size = u16(r)
        rt = i32(r+4); fk = i32(r+16); na = struct.unpack_from('<h', d, r+20)[0]
        inv = (fk >> 3) & 0xf
        ps = []
        for a in range(na):
            pp = r + size - (na - a)*12
            ps.append(f'{tdesc(i32(pp))} {name(i32(pp+4))}')
        print(f'  {INVK.get(inv, "?")}{names[j]}({", ".join(ps)}) -> {tdesc(rt)}')
    for j in range(nf, n):
        r = recs + offs[j]
        if kind == 0: print(f'  {names[j]} = {i32(r+0x10) if True else ""}')
        else: print(f'  var {names[j]}: {tdesc(i32(r+4))}')
