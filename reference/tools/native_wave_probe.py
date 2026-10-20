"""Native Wave speed setup, velocity and position integration microprobe.

Runs updateTimeMod's numerical prefix, updateJump, and update's integration
slice through its position setter. Synthetic position accessors; no level
contacts, input scheduling, portal activation, or rendering are executed.
"""
import argparse
import itertools
import json
import struct
from native_position_probe import Position
from native_velocity_probe import PLAYER,STACK,STOP,ENTRY,HASH


class Wave(Position):
 def hook(self,mu,pc,size,data):
  if pc==0x100374f10:mu.emu_stop();return
  super().hook(mu,pc,size,data)

 def sample(self,speed,mini,held,upside,x):
  self.prepare(mode='wave',vy=0,mini=mini,held=held,upside=upside)
  mu=self.mu;r=self.regs
  def scalar(index,value):mu.reg_write(getattr(r,f'UC_ARM64_REG_S{index}'),struct.unpack('<I',struct.pack('<f',value))[0])
  mu.reg_write(r.UC_ARM64_REG_X1,1);scalar(0,speed)
  mu.emu_start(0x100374e1c,STOP,count=100000)
  settings=[struct.unpack('<d',mu.mem_read(PLAYER+off,8))[0] for off in (0x780,0x788,0x790)]
  mu.reg_write(r.UC_ARM64_REG_X0,PLAYER);mu.reg_write(r.UC_ARM64_REG_SP,STACK+0xf000);mu.reg_write(r.UC_ARM64_REG_LR,STOP);scalar(0,.225)
  mu.emu_start(ENTRY,STOP,count=100000)
  velocity=struct.unpack('<d',mu.mem_read(PLAYER+0x950,8))[0]
  mu.mem_write(PLAYER,struct.pack('<Q',PLAYER+0x4000))
  for off in range(0,0x1000,8):mu.mem_write(PLAYER+0x4000+off,struct.pack('<Q',STOP+off))
  mu.mem_write(PLAYER+0x8100,struct.pack('<ff',x,150))
  mu.reg_write(r.UC_ARM64_REG_SP,STACK+0xf000);mu.reg_write(r.UC_ARM64_REG_X19,PLAYER)
  scalar(8,.25);scalar(9,.225)
  mu.emu_start(0x100375c6c,STOP,count=100000)
  return velocity,list(struct.unpack('<ff',mu.mem_read(PLAYER+0x8100,8))),settings


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('binary');parser.add_argument('--output',required=True)
 args=parser.parse_args();probe=Wave(args.binary);rows=[]
 for speed,mini,held,upside,x in itertools.product((.7,.9,1.1,1.3,1.6),(False,True),(False,True),(False,True),(0,1000,25000)):
  row=dict(speed=speed,mini=mini,held=held,upside=upside,x=x)
  try:row['native_vy'],row['native_position'],row['native_speed_settings']=probe.sample(**row)
  except Exception as error:row['unsupported']=str(error)
  rows.append(row)
 with open(args.output,'w') as output:
  json.dump(dict(binary_sha256=HASH,method='Wave speed, updateJump, position integration',limitation=__doc__,cases=rows),output,indent=2)
  output.write('\n')
 print('Recorded',sum('native_position' in row for row in rows),'of',len(rows),'Wave cases')


if __name__=='__main__':main()
