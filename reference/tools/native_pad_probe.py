"""Native yellow/pink/red pad table and state-write microprobe.

Starts GJBaseGameLayer::bumpPlayer after activation eligibility. Native pad
strength selection, PlayerObject::bumpPlayer and propellPlayer execute. Synthetic
static pad/accessors; activation callback and rotation/streak/Robot/Spider art
are bypassed. Stops after player-wrapper return, before layer event callbacks.
Both native slope flags start true. Not activation-window or full level parity.
"""
import argparse
import itertools
import json
import struct
from native_orb_probe import Orb
from native_velocity_probe import PLAYER,STOP,HASH
class Pad(Orb):
 def hook(self,mu,pc,size,data):
  if pc==0x100100630:mu.reg_write(self.regs.UC_ARM64_REG_PC,STOP);return
  if pc==0x10038fd90:mu.reg_write(self.regs.UC_ARM64_REG_PC,0x10038fe68);return
  ins=struct.unpack('<I',mu.mem_read(pc,4))[0]
  if ins&0xfffffc1f==0xd63f0000:
   target=mu.reg_read(getattr(self.regs,f'UC_ARM64_REG_X{(ins>>5)&31}'))
   if target==STOP+0x5f0:mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4);return
  super().hook(mu,pc,size,data)
 def pad(self,kind,mode,mini=False,upside=False,boost=False):
  self.kind=kind;self.prepare(mode=mode,vy=0,mini=mini,upside=upside,boost=boost)
  mu=self.mu;r=self.regs
  for pointer in (PLAYER,PLAYER+0x9000):mu.mem_write(pointer,struct.pack('<Q',PLAYER+0x4000))
  for off in range(0,0x1000,8):mu.mem_write(PLAYER+0x4000+off,struct.pack('<Q',STOP+off))
  mu.mem_write(PLAYER+0x9414,b'\x01')
  mu.mem_write(PLAYER+0x960,b'\x01\x01')
  mu.reg_write(r.UC_ARM64_REG_X19,PLAYER+0xa000);mu.reg_write(r.UC_ARM64_REG_X20,PLAYER+0x9000);mu.reg_write(r.UC_ARM64_REG_X21,PLAYER)
  mu.emu_start(0x1001004dc,STOP,count=100000)
  return struct.unpack('<d',mu.mem_read(PLAYER+0x950,8))[0],bool(mu.mem_read(PLAYER+0x902,1)[0]),bool(mu.mem_read(PLAYER+0x960,1)[0]),bool(mu.mem_read(PLAYER+0x961,1)[0])


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('binary');parser.add_argument('--output',required=True)
 args=parser.parse_args();probe=Pad(args.binary)
 probe.helpers.update({0x10038f9d0,0x10038fcac,0x10022d8a4,0x10022d93c,0x10022d91c});rows=[]
 for kind,mode,mini,upside,boost in itertools.product((8,9,34),('cube','ship','ball','ufo','wave','robot','spider','swing'),(False,True),(False,True),(False,True)):
  row=dict(kind=kind,mode=mode,mini=mini,upside=upside,boost=boost)
  try:row['native_vy'],row['native_boost'],row['native_on_slope'],row['native_was_on_slope']=probe.pad(**row)
  except Exception as error:row['unsupported']=str(error)
  rows.append(row)
 with open(args.output,'w') as output:
  json.dump(dict(binary_sha256=HASH,method='pad strength and impulse wrappers',limitation=__doc__,cases=rows),output,indent=2)
  output.write('\n')
 print('Recorded',sum('native_vy' in row for row in rows),'of',len(rows),'pad cases')


if __name__=='__main__':main()
