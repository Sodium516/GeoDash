"""Native flight-rotation microprobe with synthetic position/angle accessors.

Executes updateShipRotation and its original Slerp2D helper. External libm
atan2f, sincosf, acosf and sinf use Python math rounded to float32, so results
include that adapter's numerical limits. No full gameplay/collision parity claim.
"""
import argparse
import itertools
import json
import math
import struct
from native_contact_probe import Contact
from native_velocity_probe import PLAYER,STOP,HASH
class Rotation(Contact):
 def f(self,index):return struct.unpack('<f',struct.pack('<I',self.mu.reg_read(getattr(self.regs,f'UC_ARM64_REG_S{index}'))))[0]
 def putf(self,index,value):self.mu.reg_write(getattr(self.regs,f'UC_ARM64_REG_S{index}'),struct.unpack('<I',struct.pack('<f',value))[0])
 def hook(self,mu,pc,size,data):
  ins=struct.unpack('<I',mu.mem_read(pc,4))[0]
  if ins&0xfffffc1f==0xd63f0000:
   target=mu.reg_read(getattr(self.regs,f'UC_ARM64_REG_X{(ins>>5)&31}'))
   if target==STOP+0x160:self.putf(0,self.rotation);mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4);return
   if target==STOP+0x158:self.rotation=self.f(0);mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4);return
  if ins&0xfc000000==0x94000000:
   imm=ins&0x3ffffff
   if imm&0x2000000:imm-=0x4000000
   target=pc+imm*4
   if target==0x1006d1e38:
    value=self.f(0);self.putf(0,math.sin(value));self.putf(1,math.cos(value));mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4);return
   if target in (0x1006d1e8c,0x1006d2768):
    self.putf(0,math.acos(max(-1,min(1,self.f(0)))) if target==0x1006d1e8c else math.sin(self.f(0)));mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4);return
   if target==0x1006d1eb0:
    self.putf(0,math.atan2(self.f(0),self.f(1)));mu.reg_write(self.regs.UC_ARM64_REG_PC,pc+4);return
  super().hook(mu,pc,size,data)
 def angle(self,mode,dy,rotation=0,mini=False,upside=False):
  self.prepare(mode=mode,vy=0,mini=mini,upside=upside)
  mu=self.mu;r=self.regs;self.rotation=rotation
  mu.mem_write(PLAYER,struct.pack('<Q',PLAYER+0x4000))
  for off in range(0,0x1000,8):mu.mem_write(PLAYER+0x4000+off,struct.pack('<Q',STOP+off))
  mu.mem_write(PLAYER+0x8100,struct.pack('<ff',1.3,150+dy))
  mu.mem_write(PLAYER+0x9a8,struct.pack('<ff',0,150))
  self.putf(0,.25)
  mu.emu_start(0x100382970,STOP,count=100000)
  return self.rotation


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('binary');parser.add_argument('--output',required=True)
 args=parser.parse_args();probe=Rotation(args.binary);probe.helpers.add(0x10022515c);rows=[]
 for mode,mini,upside,dy,rotation in itertools.product(('ship','ufo','wave','swing'),(False,True),(False,True),(-3,-1,0,1,3),(-170,0,20,170)):
  row=dict(mode=mode,mini=mini,upside=upside,dy=dy,rotation=rotation)
  try:row['native_rotation']=probe.angle(**row)
  except Exception as error:row['unsupported']=str(error)
  rows.append(row)
 with open(args.output,'w') as output:
  json.dump(dict(binary_sha256=HASH,method='updateShipRotation',native_dt=.25,dx=1.3,limitation=__doc__,cases=rows),output,indent=2)
  output.write('\n')
 print('Recorded',sum('native_rotation' in row for row in rows),'of',len(rows),'rotation cases')


if __name__=='__main__':main()
