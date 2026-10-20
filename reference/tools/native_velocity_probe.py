"""Read-only velocity microprobe for the installed macOS Geometry Dash 2.2081.

Requires optional Unicorn 2.1.4 (not a game dependency). Run with Python's
PYTHONPATH pointing at that installation. No original executable bytes are saved
or distributed. A known binary hash guards the fixed offsets. This executes only
updateJump and whitelisted helpers, with a minimal player object; it does not
simulate positions, collisions, rendering, input scheduling, or a complete game.
"""
import argparse
import hashlib
import json
import itertools
from pathlib import Path
import struct

HASH='dc79491d886eedfc1f2be4ef6ae5c660f86470ee0e442b42ac97d793f031ad52'
ENTRY=0x1003766e8
PLAYER=0x200000000
STACK=0x300000000
STOP=0x400000000
FLAGS={'ship':0x969,'ufo':0x96a,'ball':0x96b,'wave':0x96c,'robot':0x96d,'spider':0x96e,'swing':0x974}


def arm64_slice(raw):
    if raw[:4]==b'\xca\xfe\xba\xbe':
        count=struct.unpack_from('>I',raw,4)[0]
        for index in range(count):
            cpu,subtype,offset,size,align=struct.unpack_from('>IIIII',raw,8+20*index)
            if cpu==0x100000c:return raw[offset:offset+size]
        raise ValueError('No ARM64 slice found')
    if raw[:4]!=b'\xcf\xfa\xed\xfe':raise ValueError('Expected 64-bit Mach-O or fat executable')
    return raw


class Probe:
    def __init__(self,binary):
        from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
        from unicorn import arm64_const as regs
        self.regs=regs
        raw=arm64_slice(Path(binary).read_bytes())
        if hashlib.sha256(raw).hexdigest()!=HASH:
            raise ValueError('Unsupported executable hash; offsets must be revalidated for this game version')
        self.mu=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
        offset=32
        for _ in range(struct.unpack_from('<I',raw,16)[0]):
            cmd,size=struct.unpack_from('<II',raw,offset)
            if cmd==0x19:
                name,address,vsize,fileoff,filesize=struct.unpack_from('<16sQQQQ',raw,offset+8)
                if vsize and address:
                    self.mu.mem_map(address,(vsize+4095)//4096*4096)
                    if filesize:self.mu.mem_write(address,raw[fileoff:fileoff+filesize])
            offset+=size
        self.mu.mem_map(PLAYER,0x10000)
        self.mu.mem_map(STACK,0x10000)
        self.mu.mem_map(STOP,0x1000)
        self.mu.hook_add(UC_HOOK_CODE,self.hook)
        self.helpers={0x10037570c,0x100374ddc,0x1003793cc,0x10037ba64,0x1003793e0}

    def hook(self,mu,pc,size,data):
        instruction=struct.unpack('<I',mu.mem_read(pc,4))[0]
        if instruction&0xfc000000==0x94000000:
            imm=instruction&0x3ffffff
            if imm&0x2000000:imm-=0x4000000
            target=pc+imm*4
            if target==0x1006d2720:  # rand: only seeds the obfuscated grounded flag
                mu.reg_write(self.regs.UC_ARM64_REG_X0,0)
                mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4)
            elif target not in self.helpers:
                raise RuntimeError(f'Unsupported helper call {pc:x} -> {target:x}')
        elif instruction&0xfffffc1f==0xd63f0000:
            raise RuntimeError(f'Unsupported virtual call at {pc:x}')

    def prepare(self,mode,vy,held=False,mini=False,upside=False,boost=False,fixed=False,dual=False):
        mu=self.mu;r=self.regs
        mu.mem_write(PLAYER,bytes(0x10000))
        mu.mem_write(STACK,bytes(0x10000))
        for index in range(31):mu.reg_write(getattr(r,f'UC_ARM64_REG_X{index}'),0)
        fields={0x790:('d',.9581990242004395),0x788:('d',11.180031776428223),
                0x780:('d',5.7700018882751465),0x9a0:('f',.6 if mini else 1.),
                0x9a4:('f',.9),0xb1c:('f',1.),0x950:('d',vy),
                0x935:('B',int(held)),0x96f:('B',int(upside)),0x902:('B',int(boost)),
                0x559:('B',int(fixed)),0xa31:('B',int(dual))}
        if mode in FLAGS:fields[FLAGS[mode]]=('B',1)
        for off,(fmt,value) in fields.items():mu.mem_write(PLAYER+off,struct.pack('<'+fmt,value))
        mu.reg_write(r.UC_ARM64_REG_SP,STACK+0xf000)
        mu.reg_write(r.UC_ARM64_REG_LR,STOP)
        mu.reg_write(r.UC_ARM64_REG_X0,PLAYER)
        mu.reg_write(r.UC_ARM64_REG_S0,struct.unpack('<I',struct.pack('<f',.225))[0])

    def step(self,**fields):
        self.prepare(**fields)
        mu=self.mu;r=self.regs
        mu.emu_start(ENTRY,STOP,count=100000)
        if mu.reg_read(r.UC_ARM64_REG_PC)!=STOP:raise RuntimeError('Native routine did not return within instruction limit')
        return struct.unpack('<d',mu.mem_read(PLAYER+0x950,8))[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    probe=Probe(args.binary)
    rows=[]
    for mode in ('cube','ball','ship','ufo','swing'):
        for mini in (False,True):
            for upside in (False,True):
                for held in (False,True):
                    variants=itertools.product((False,True),repeat=3) if mode in ('ship','ufo','swing') else [(False,False,False)]
                    for boost,fixed,dual in variants:
                        for vy in (-10.,-6.4,-3.,0.,1.9,2.,7.,8.,10.):
                            row=dict(mode=mode,mini=mini,upside=upside,held=held,vy=vy,
                                     boost=boost,fixed=fixed,dual=dual)
                            try:row['native_vy']=probe.step(**row)
                            except Exception as error:row['unsupported']=str(error)
                            rows.append(row)
    report=dict(binary_sha256=HASH,method='PlayerObject::updateJump',dt=.225,
                limitation='Velocity-only microprobe with minimal player state; not full engine parity',cases=rows)
    text=json.dumps(report,indent=2)+'\n'
    if args.output:args.output.write_text(text)
    else:print(text,end='')
    print('Probed',sum('native_vy' in row for row in rows),'of',len(rows),'cases')


if __name__=='__main__':main()
