"""Isolated native contact microprobe; NOT the complete collision pipeline.

Requires the same optional Unicorn setup and binary hash as native_velocity_probe.
A null GameObject and explicit static rectangle deliberately bypass object state
and the caller's collision candidate filters. The virtual methods supply synthetic
position, rectangle and zero rotation. Never infer full gameplay collision rules
from these samples alone; a direct broad-snap translation regressed known routes.
"""
import argparse
import json
import struct
from native_velocity_probe import Probe,PLAYER,STOP,HASH
class Contact(Probe):
 """Execute only isolated static-rectangle contacts, with synthetic accessors."""
 def hook(self,mu,pc,size,data):
  ins=struct.unpack('<I',mu.mem_read(pc,4))[0]
  if ins&0xfffffc1f==0xd63f0000:
   register=(ins>>5)&31
   target=mu.reg_read(getattr(self.regs,f'UC_ARM64_REG_X{register}'))
   if target==STOP+0x520:
    object_call=mu.reg_read(self.regs.UC_ARM64_REG_X0)==PLAYER+0x9000
    mu.reg_write(self.regs.UC_ARM64_REG_X0,PLAYER+(0x8300 if object_call else 0x8000))
   elif target==STOP+0x6f8:
    pointer=mu.reg_read(self.regs.UC_ARM64_REG_X0)
    mu.reg_write(self.regs.UC_ARM64_REG_X0,struct.unpack('<I',mu.mem_read(pointer+0x398,4))[0])
   elif target==STOP+0x540:
    # Static object's real and previous positions agree; no movement helpers.
    mu.mem_write(mu.reg_read(self.regs.UC_ARM64_REG_X8),bytes(mu.mem_read(PLAYER+0x94c8,8)))
   elif target==STOP+0xc0:mu.reg_write(self.regs.UC_ARM64_REG_X0,PLAYER+0x8100)
   elif target==STOP+0x528:
    # CCRect returned indirectly in x8; original caller supplies scale in s0/s1.
    x,y=struct.unpack('<ff',mu.mem_read(PLAYER+0x8100,8))
    sx=struct.unpack('<f',struct.pack('<I',mu.reg_read(self.regs.UC_ARM64_REG_S0)))[0]
    sy=struct.unpack('<f',struct.pack('<I',mu.reg_read(self.regs.UC_ARM64_REG_S1)))[0]
    mu.mem_write(mu.reg_read(self.regs.UC_ARM64_REG_X8),struct.pack('<ffff',x-15*sx,y-15*sy,30*sx,30*sy))
   elif target==STOP+0x160:mu.reg_write(self.regs.UC_ARM64_REG_S0,0)
   elif target==STOP+0xb8:
    ptr=mu.reg_read(self.regs.UC_ARM64_REG_X1);position=bytes(mu.mem_read(ptr,8));mu.mem_write(PLAYER+0x8100,position)
    x,y=struct.unpack('<ff',position);mu.mem_write(PLAYER+0x8000,struct.pack('<ffff',x-15,y-15,30,30))
   else:raise RuntimeError(f'Unsupported virtual {pc:x} slot {target-STOP:x}')
   mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4);return
  if ins&0xfc000000==0x94000000:
   imm=ins&0x3ffffff
   if imm&0x2000000:imm-=0x4000000
   target=pc+imm*4
   if 0x10022d000<=target<0x10022e000:return
  super().hook(mu,pc,size,data)
 def contact(self,x,y,old_y,vy,rect,upside=True,object_mode=False):
  self.prepare(mode='cube',vy=vy,upside=upside)
  mu=self.mu;r=self.regs
  mu.mem_write(PLAYER+0x6f3,b'\x01')
  mu.mem_write(PLAYER,struct.pack('<Q',PLAYER+0x4000))
  for off in range(0,0x1000,8):mu.mem_write(PLAYER+0x4000+off,struct.pack('<Q',STOP+off))
  mu.mem_write(PLAYER+0x8000,struct.pack('<ffff',x-15,y-15,30,30))
  mu.mem_write(PLAYER+0x8100,struct.pack('<ff',x,y))
  mu.mem_write(PLAYER+0x8200,struct.pack('<ffff',*rect))
  if object_mode:
   self.helpers.update({0x1004fa164,0x1004ef7cc})
   mu.mem_write(PLAYER+0x8300,struct.pack('<ffff',*rect))
   mu.mem_write(PLAYER+0x8200,bytes(16))
   mu.mem_write(PLAYER+0x9000,struct.pack('<Q',PLAYER+0x4000))
   mu.mem_write(PLAYER+0x94c8,struct.pack('<ff',rect[0]+rect[2]/2,rect[1]+rect[3]/2))
  mu.mem_write(PLAYER+0x4cc,struct.pack('<f',old_y))
  mu.reg_write(r.UC_ARM64_REG_X1,PLAYER+0x9000 if object_mode else 0);mu.reg_write(r.UC_ARM64_REG_X2,PLAYER+0x8200);mu.reg_write(r.UC_ARM64_REG_X3,0)
  mu.emu_start(0x10037f8e4,STOP,count=100000)
  if mu.reg_read(r.UC_ARM64_REG_PC)!=STOP:raise RuntimeError('Native contact instruction limit exceeded')
  return dict(result=mu.reg_read(r.UC_ARM64_REG_X0),y=struct.unpack('<f',mu.mem_read(PLAYER+0x8104,4))[0],vy=struct.unpack('<d',mu.mem_read(PLAYER+0x950,8))[0])



def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('binary')
 parser.add_argument('--output',required=True)
 parser.add_argument('--object',action='store_true',help='Supply a synthetic static solid GameObject')
 args=parser.parse_args()
 probe=Contact(args.binary)
 probe.helpers.update({0x100382fbc,0x100381ea0,0x100383370,0x1003833fc})
 rows=[]
 for upside in (False,True):
  for y in range(120,191,5):
   for vy in (-5,5):
    row=dict(x=1030,y=y,old_y=y-vy*.225,vy=vy,rect=[1020,140,30,30],upside=upside,object_mode=args.object)
    try:row['native']=probe.contact(**row)
    except Exception as error:row['unsupported']=str(error)
    rows.append(row)
 with open(args.output,'w') as output:
  json.dump(dict(binary_sha256=HASH,method='PlayerObject::collidedWithObjectInternal',
   limitation='Isolated contact with synthetic accessors and optional static solid object; not full contact pipeline or level parity',cases=rows),output,indent=2)
  output.write('\n')
 print('Recorded',sum('native' in row for row in rows),'supported contacts of',len(rows))


if __name__=='__main__':main()
