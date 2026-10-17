import struct, zlib, zipfile, os, re
BASE="/mnt/c/Users/wesle/dev/ports/Banjo-Kazooie (BR)/lighthouse"
BR_ROM=os.path.join(BASE,"Banjo-Kazooie (BR).z64")
US_O2R=os.path.join(BASE,"bk.o2r")
BR_O2R="/tmp/torch-br/out/bk.o2r"
OUT=os.path.join(BASE,"mods","~lang","bk_pt-BR.o2r")
HDR=64

def bk_unzip_at(rom,off,sz):
    d=rom[off:off+sz]
    assert d[0]==0x11 and d[1]==0x72, hex(off)
    return zlib.decompress(bytes(d[6:]),wbits=-15)

def rdstr(buf,pos,n):
    out=[]
    for _ in range(n):
        if pos+2>len(buf): break
        c=buf[pos]; ln=buf[pos+1]; pos+=2
        out.append((c,bytes(buf[pos:pos+ln]))); pos+=ln
    return out,pos

def parse_langblock(raw,pos):
    bot=[];top=[]
    n=raw[pos];pos+=1
    for _ in range(n):
        if pos+2>len(raw):break
        c=raw[pos];l=raw[pos+1];pos+=2
        bot.append((c,bytes(raw[pos:pos+l])));pos+=l
    if n==0 and pos+3<=len(raw) and raw[pos]==4 and raw[pos+1]==1 and raw[pos+2]==0: pos+=3
    if pos<len(raw):
        n2=raw[pos];pos+=1
        for _ in range(n2):
            if pos+2>len(raw):break
            c=raw[pos];l=raw[pos+1];pos+=2
            top.append((c,bytes(raw[pos:pos+l])));pos+=l
        if n2==0 and pos+3<=len(raw) and raw[pos]==4 and raw[pos+1]==1 and raw[pos+2]==0: pos+=3
    return bot,top

def parse_quiz(raw):
    pos=9; ts=raw[pos];pos+=1
    text,pos=rdstr(raw,pos,ts-3)
    opts,pos=rdstr(raw,pos,3)
    return text,opts

def parse_grunty(raw):
    pos=9; ts=raw[pos];pos+=1
    text,pos=rdstr(raw,pos,ts-3)
    opts=[]
    for _ in range(3):
        if pos+4>len(raw):break
        c=raw[pos];sl=raw[pos+1];u0=raw[pos+2];u1=raw[pos+3];pos+=4
        s=bytes(raw[pos:pos+max(0,sl-2)]);pos+=max(0,sl-2)
        opts.append((c,s,u0,u1))
    return text,opts

def wrentries(es):
    o=bytearray();o+=struct.pack('<I',len(es))
    for c,s in es:
        o+=struct.pack('B',c)+struct.pack('<I',len(s))+s
    return bytes(o)
def bd(bot,top): return struct.pack('<I',1)+wrentries(bot)+wrentries(top)
def bq(text,opts): return struct.pack('<I',1)+wrentries(text)+wrentries(opts)
def bg(text,opts):
    o=bytearray();o+=struct.pack('<I',1)+wrentries(text)+struct.pack('<I',len(opts))
    for c,s,u0,u1 in opts:
        o+=struct.pack('B',c)+struct.pack('B',u0)+struct.pack('B',u1)+struct.pack('<I',len(s))+s
    return bytes(o)

# strings de UI (ASCII puro: fonte bold 0x6EC nao tem acentos PT-BR)
UI = [
 ("USE THE CONTROL STICK TO SELECT A GAME.","USE O ANALOGICO PARA ESCOLHER UM JOGO."),
 ("PRESS A TO PLAY THE GAME OR Z TO ERASE IT!","APERTE A PARA JOGAR OU Z PARA APAGAR!"),
 ("ARE YOU SURE? PRESS A TO CONFIRM, OR B TO CANCEL.","TEM CERTEZA? APERTE A PARA CONFIRMAR OU B PARA CANCELAR."),
 ("GAME ","JOGO "),
 (": EMPTY",": VAZIO"),
 (": TIME ",": TEMPO "),
 (" JIGSAW"," QUEBRA-CABECA"),
 (" JIGSAWS"," QUEBRA-CABECAS"),
 (" NOTE"," NOTA"),
 (" NOTES"," NOTAS"),
 ("RETURN TO GAME","VOLTAR AO JOGO"),
 ("EXIT TO WITCH'S LAIR","SAIR PARA O COVIL DA BRUXA"),
 ("VIEW TOTALS","VER TOTAIS"),
 ("SAVE AND QUIT","SALVAR E SAIR"),
 ("ARE YOU SURE?","TEM CERTEZA?"),
 ("A - YES, B - NO","A - SIM, B - NAO"),
]

pal=open(os.path.join(BASE,'assets/yaml/pal/rev0/assets.yaml'),encoding='utf-8',errors='replace').read()
sym={}
for m in re.finditer(r'^\s*(\d+):\s*(\S+)\s*$',pal,re.M): sym[int(m.group(1))]=m.group(2)
us1=open(os.path.join(BASE,'assets/yaml/us/rev1/assets.yaml'),encoding='utf-8',errors='replace').read()
sym_us={}
for m in re.finditer(r'^\s*(\d+):\s*(\S+)\s*$',us1,re.M): sym_us[int(m.group(1))]=m.group(2)
catof=lambda s: s.split('/')[0]
ids=[i for i,s in sym.items() if s.startswith(('dialog/','quizq/','gruntyq/'))]
ok=[];ex=[]
for i in sorted(ids):
    sp=sym[i]; su=sym_us.get(i)
    if su is None: ex.append((i,sp,'sem base US')); continue
    if catof(sp)!=catof(su): ex.append((i,sp,'tipo diverge')); continue
    ok.append(i)
br=open(BR_ROM,'rb').read()
count=struct.unpack('>I',br[0x5E90:0x5E94])[0]
ds=0x5E90+8+count*8
ents=[struct.unpack('>Ihh',br[0x5E98+i*8:0x5E98+i*8+8]) for i in range(count)]
def szof(i):
    b=ents[i][0];c=[e[0] for e in ents if e[0]>b];return (min(c)-b) if c else 0
z=zipfile.ZipFile(US_O2R)
hdr={}
for n in z.namelist():
    if '/dialog/' in n: hdr.setdefault('dialog',z.read(n)[:HDR])
    elif '/quizq/' in n: hdr.setdefault('quizq',z.read(n)[:HDR])
    elif '/gruntyq/' in n: hdr.setdefault('gruntyq',z.read(n)[:HDR])
brz=zipfile.ZipFile(BR_O2R)
font=[n for n in brz.namelist() if 'ASSET_6EB' in n]
os.makedirs(os.path.dirname(OUT),exist_ok=True)
oz=zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED)
for n in ['portVersion','assets/portVersion']:
    try: oz.writestr(n,z.read(n))
    except KeyError: pass
oz.writestr('version', bytes([1])+struct.pack('>I',0xB1CC3F73))
# langinfo + strings
li=bytearray()
li+=struct.pack('<I',1)+struct.pack('<I',1)+struct.pack('<I',0)+struct.pack('<I',0)
name=b'Portuguese (BR)'; li+=struct.pack('<I',len(name))+name
li+=struct.pack('<I',len(UI))
for k,v in UI:
    kb=k.encode('ascii'); vb=v.encode('ascii')
    li+=struct.pack('<I',len(kb))+kb+struct.pack('<I',len(vb))+vb
oz.writestr('langinfo',bytes(li))
okc=0;fails=[]
for i in ok:
    nm=sym[i];cat=catof(nm)
    b,comp,t=ents[i]
    if t==4 or comp==0: continue
    sz=szof(i)
    if sz<=0: fails.append((i,nm,'size0'));continue
    try:
        raw=bk_unzip_at(br,ds+b,sz);h=bytes(raw[:3])
        if cat=='dialog':
            if h==b'\x03\x07\x00': bot,top=parse_langblock(raw,7)
            elif h==b'\x01\x03\x00': bot,top=parse_langblock(raw,3)
            else: fails.append((i,nm,'hdr'));continue
            if not bot: bot=[(4,b'\x00')]
            if not top: top=[(4,b'\x00')]
            payload=hdr['dialog']+bd(bot,top)
        elif cat=='quizq':
            tx,op=parse_quiz(raw); payload=hdr['quizq']+bq(tx,op)
        elif cat=='gruntyq':
            tx,op=parse_grunty(raw); payload=hdr['gruntyq']+bg(tx,op)
        else: continue
        oz.writestr('assets/'+nm,payload); okc+=1
    except Exception as e:
        fails.append((i,nm,str(e)[:60]))
for n in font:
    oz.writestr(n, brz.read(n))
oz.close();brz.close()
print('texto OK:',okc,'| font:',len(font),'| fail:',len(fails))
print('excluidos:',ex)
print('UI strings:',len(UI))
print('tamanho:',os.path.getsize(OUT))
