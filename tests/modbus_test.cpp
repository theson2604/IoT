#include "Modbus.h"
#include <assert.h>
#include <stdio.h>
struct Mock : mb::Transport {
 unsigned calls=0;uint8_t outputs=0,inputs=0xa5;int fault=0;bool ignoreWrite=false;
 size_t exchange(const uint8_t* q,size_t n,uint8_t* p,size_t,uint32_t timeout)override{
  ++calls;assert(n==8&&mb::crc(q,n)==0&&timeout==300);
  if(fault==1||(fault==2&&calls==1))return 0;
  p[0]=q[0];p[1]=q[1];
  if(fault==3){p[1]|=0x80;p[2]=2;return mb::seal(p,3);}
  size_t len;
  if(q[1]==5){assert(q[2]==0&&q[3]<8);if(!ignoreWrite){if(q[4]==255)outputs|=1<<q[3];else outputs&=~(1<<q[3]);}memcpy(p,q,8);len=8;}
  else {assert(q[2]==0&&q[3]==0&&q[4]==0&&q[5]==8);p[2]=1;p[3]=q[1]==1?outputs:inputs;len=mb::seal(p,4);}
  if(fault==4)p[len-1]^=1;
  if(fault==5){p[0]=2;mb::seal(p,len-2);}
  if(fault==6){p[1]=3;mb::seal(p,len-2);}
  if(fault==7){p[2]=2;mb::seal(p,len-2);}
  if(fault==8&&q[1]==5){p[3]^=1;mb::seal(p,6);}
  return len;
 }
};
int main(){
 uint8_t known[]={1,5,0,0,255,0};assert(mb::crc(known,6)==0x3a8c);
 Mock d;mb::Master m(d);assert(m.read(1).value==0);assert(m.read(2).value==0xa5);
 unsigned before=d.calls;assert(m.write(1,true).error==mb::Error::Blocked);assert(d.calls==before&&d.outputs==0);
 assert(m.write(1,true,false).error==mb::Error::Ok&&d.outputs==1);
 assert(m.write(1,false,false).error==mb::Error::Ok&&d.outputs==0);
 assert(m.write(0,true,false).error==mb::Error::Argument);assert(m.write(9,true,false).error==mb::Error::Argument);assert(m.read(3).error==mb::Error::Argument);
 for(int f=1;f<=8;f++){Mock x;x.fault=f;mb::Master a(x);auto r=f==8?a.write(1,true,false):a.read(1);
  if(f==2)assert(r.error==mb::Error::Ok&&r.attempts==2);
  else if(f==3)assert(r.error==mb::Error::Exception&&r.exception==2&&x.calls==1);
  else {assert(r.error!=mb::Error::Ok&&r.attempts==3);}}
 Mock x;x.ignoreWrite=true;mb::Master a(x);assert(a.write(1,true,false).error==mb::Error::Readback);
 puts("PASS: CRC vector, FC01/02/05, safety, bounds, timeout/retry, exception, malformed frames, echo, readback");
}
