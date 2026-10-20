"""Native orb impulse slice with synthetic static orb type/accessors.

Starts after ring activation bookkeeping and stops after velocity/gravity writes,
after boost writes; Robot/Spider sprite work is explicitly bypassed. Skips statistics, rotations and streak effects using
native_ground_probe's exclusions. Empty collision logs and manager/layer state.
These validate the impulse table, not orb activation timing or full level parity.
"""
import argparse
import itertools
import json
import struct
from native_ground_probe import Flap
from native_velocity_probe import PLAYER,STOP,HASH
class Orb(Flap):
 def hook(self,mu,pc,size,data):
  if pc==0x10038a468:
   mu.reg_write(self.regs.UC_ARM64_REG_PC,0x10038a504);return
  if pc==0x100389ef0:mu.reg_write(self.regs.UC_ARM64_REG_PC,STOP);return
  ins=struct.unpack('<I',mu.mem_read(pc,4))[0]
  if ins&0xfffffc1f==0xd63f0000:
   target=mu.reg_read(getattr(self.regs,f'UC_ARM64_REG_X{(ins>>5)&31}'))
   if target==STOP+0x6f8:mu.reg_write(self.regs.UC_ARM64_REG_X0,self.kind)
   elif target==STOP+0xc0:mu.reg_write(self.regs.UC_ARM64_REG_X0,PLAYER+0x8100)
   else:raise RuntimeError(f'Unsupported virtual {pc:x}: {target:x}')
   mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4);return
  if ins&0xfc000000==0x94000000:
   imm=ins&0x3ffffff
   if imm&0x2000000:imm-=0x4000000
   target=pc+imm*4
   if target==0x100300128:
    mu.reg_write(self.regs.UC_ARM64_REG_X0,PLAYER+0xa000);mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4);return
   if target in (0x10037bebc,0x10037afbc):
    mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4);return
  super().hook(mu,pc,size,data)
 def impulse(self,kind,mode,mini=False,upside=False,boost=False):
  self.kind=kind;self.prepare(mode=mode,vy=0,mini=mini,upside=upside,boost=boost)
  mu=self.mu;r=self.regs
  mu.mem_write(PLAYER,struct.pack('<Q',PLAYER+0x4000));mu.mem_write(PLAYER+0x9000,struct.pack('<Q',PLAYER+0x4000))
  for off in range(0,0x1000,8):mu.mem_write(PLAYER+0x4000+off,struct.pack('<Q',STOP+off))
  for off in (0x5a8,0x5b0,0x5b8,0x5c0):mu.mem_write(PLAYER+off,struct.pack('<Q',PLAYER+0x7000))
  mu.reg_write(r.UC_ARM64_REG_X19,PLAYER);mu.reg_write(r.UC_ARM64_REG_X20,PLAYER+0x9000)
  mu.emu_start(0x100389d24 if kind==32 else 0x100389d9c,STOP,count=100000)
  return struct.unpack('<d',mu.mem_read(PLAYER+0x950,8))[0],bool(mu.mem_read(PLAYER+0x96f,1)[0]),bool(mu.mem_read(PLAYER+0x902,1)[0])


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('binary');parser.add_argument('--output',required=True)
 args=parser.parse_args();probe=Orb(args.binary)
 probe.helpers.update({0x10037b40c,0x10029cf24,0x10022d91c});rows=[]
 for kind,mode,mini,upside,boost in itertools.product((11,12,13,29,32,35),('cube','ship','ball','ufo','wave','robot','spider','swing'),(False,True),(False,True),(False,True)):
  row=dict(kind=kind,mode=mode,mini=mini,upside=upside,boost=boost)
  try:
   row['native_vy'],row['native_upside'],row['native_boost']=probe.impulse(**row)
  except Exception as error:row['unsupported']=str(error)
  rows.append(row)
 with open(args.output,'w') as output:
  json.dump(dict(binary_sha256=HASH,method='ringJump impulse slice',limitation=__doc__,cases=rows),output,indent=2)
  output.write('\n')
 print('Recorded',sum('native_vy' in row for row in rows),'of',len(rows),'orb impulse cases')


if __name__=='__main__':main()
